"""One-shot migration of the SQLite database into PostgreSQL.

    python tools/migrate_sqlite_to_postgres.py \
        --source database/classpilot.db \
        --target postgresql+psycopg://campuspilot:campuspilot@localhost:5432/campuspilot

Run it with ``--dry-run`` first. It reports what it would copy without writing.

Design notes, because a data migration is unforgiving in both directions:

* **Ids are preserved.** Foreign keys are copied as-is, so re-numbering would
  silently re-point every ``feedback.user_id`` at a different student. Explicit
  primary keys mean the SERIAL sequences are *not* advanced by the insert, so
  ``_reset_sequences`` fixes them afterwards. Miss that and the first signup
  after the cutover dies with a duplicate-key error.

* **Coercion is driven by the target column types, not guessed per table.**
  SQLite is dynamically typed and hands back a ``str`` for a DATE, a ``0`` for a
  BOOLEAN, and JSON as text. Rather than special-casing twenty tables, this
  walks the SQLModel metadata and applies the right converter per column type.
  A new column added to a model is handled automatically.

* **Tables are copied parents-first.** ``SQLModel.metadata.sorted_tables`` is a
  topological sort, so a child row never lands before the parent it references.

* **Row counts are verified.** Every table's source and destination counts are
  printed and any mismatch is a hard failure, because a silent partial copy is
  the worst possible outcome for this script.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sqlite3
import sys
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import sqlalchemy as sa
from sqlmodel import SQLModel

# Importing models is what populates SQLModel.metadata.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend" / "backend"))

import models  # noqa: E402,F401


# ---------------------------------------------------------------------------
# Value coercion
# ---------------------------------------------------------------------------

def _coerce(value: Any, coltype: Any) -> Any:
    """Convert one SQLite value into something the Postgres column accepts.

    SQLite returns everything as str/int/float/bytes/None. The target column
    type says what it actually needs, which is the only reliable signal available.

    Checks are isinstance against the SQLAlchemy type classes rather than
    ``coltype.python_type``: that property raises NotImplementedError on several
    types (JSON among them), which turns a routine copy into a traceback.
    """
    if value is None:
        return None

    # sa.JSON is the base of both sqlalchemy.JSON and postgresql.JSONB, so this
    # one check covers every JSON column on either dialect.
    if isinstance(coltype, sa.JSON):
        # SQLite stored this as TEXT. Parse it so the Postgres JSON column gets a
        # real structure rather than a doubly-encoded JSON string.
        return json.loads(value) if isinstance(value, (str, bytes)) else value

    # DateTime before Date: a datetime is not a date instance, but a TIMESTAMP
    # column declared sa.Date on some drivers needs the narrower check first.
    if isinstance(coltype, sa.DateTime):
        return value if isinstance(value, dt.datetime) else dt.datetime.fromisoformat(str(value))

    if isinstance(coltype, sa.Date):
        return value if isinstance(value, dt.date) else dt.date.fromisoformat(str(value))

    if isinstance(coltype, sa.Time):
        return value if isinstance(value, dt.time) else dt.time.fromisoformat(str(value))

    if isinstance(coltype, sa.Boolean):
        # SQLite has no boolean type; it stores 0/1 as integers.
        return bool(value)

    # sa.Enum needs no conversion: SQLAlchemy persists the member *name*, which is
    # what the SQLite file already holds.
    return value


def _row_values(row: sqlite3.Row, table: sa.Table) -> tuple[dict[str, Any], int]:
    """Map one source row onto target columns, coercing each value.

    Returns ``(values, repairs)`` where ``repairs`` counts NOT NULL columns that
    arrived NULL and were filled from the model default.
    """
    out: dict[str, Any] = {}
    repairs = 0
    for col in table.columns:
        present = col.name in row.keys()
        value = row[col.name] if present else None

        if not col.nullable and value is None and col.default is not None \
                and getattr(col.default, "is_scalar", False):
            # This is real historical damage, not a hypothetical.
            #
            # `user.role` is declared NOT NULL, but the old SQLite schema-repair
            # pass emitted `ALTER TABLE user ADD COLUMN "role" VARCHAR` - only
            # the compiled *type*, silently dropping NOT NULL. Rows that already
            # existed when that column was added got NULL, and SQLite stored it
            # happily. PostgreSQL rejects the insert outright.
            #
            # Filling from the model default is the only safe repair: it is what
            # the column would have held for a row created after the column
            # existed. Counted and reported rather than done quietly - a data
            # migration must never silently invent values.
            value = col.default.arg
            repairs += 1

        out[col.name] = _coerce(value, col.type)
    return out, repairs


def _model_defaults(table: sa.Table) -> dict[str, Any]:
    """Scalar defaults declared on the model, for reporting."""
    return {
        c.name: c.default.arg
        for c in table.columns
        if c.default is not None and getattr(c.default, "is_scalar", False)
    }


# ---------------------------------------------------------------------------
# Sequences
# ---------------------------------------------------------------------------

def _reset_sequences(conn: sa.Connection, target: sa.Engine) -> None:
    """Advance every SERIAL past the highest id we inserted.

    Without this the sequence still says "next id = 1" while the table is full of
    ids carried over from the SQLite file, and the first INSERT after cutover
    raises DuplicateKey. That is the most common way a data migration fails
    *after* reporting success.

    Two subtleties, both learned the hard way:

    * Table names are read from metadata and quoted by SQLAlchemy rather than
      interpolated. The `user` table is a reserved word in PostgreSQL, so
      `SELECT MAX(id) FROM user` is a syntax error.
    * ``setval`` is a plain function call, so its sequence name is bound as a
      *parameter*. Only the max-value lookup needs SQL.
    """
    inspector = sa.inspect(target)
    existing = set(inspector.get_table_names())

    for table in SQLModel.metadata.sorted_tables:
        if table.name not in existing:
            continue

        pk_cols = list(table.primary_key.columns)
        if len(pk_cols) != 1 or not isinstance(pk_cols[0].type, sa.Integer):
            continue
        pk = pk_cols[0]

        seq_name = conn.execute(
            sa.text("SELECT pg_get_serial_sequence(:table, :column)"),
            {"table": table.name, "column": pk.name},
        ).scalar()
        if not seq_name:
            continue

        # Highest id actually present. Quoted by SQLAlchemy, so `user` works.
        max_id = conn.execute(sa.select(sa.func.max(table.c[pk.name]))).scalar()

        # setval(seq, n, true) -> next value is n+1, which is what we want when
        # rows exist. With no rows, next value 1 is correct, and the explicit
        # `false` flag keeps it from skipping id 1.
        conn.execute(
            sa.text("SELECT setval(:seq, :val, :called)"),
            {"seq": seq_name, "val": int(max_id) if max_id is not None else 1,
             "called": max_id is not None},
        )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def migrate(source: Path, target_url: str, dry_run: bool = False) -> int:
    if not source.exists():
        print(f"source not found: {source}", file=sys.stderr)
        return 2

    src = sqlite3.connect(f"file:{source}?mode=ro", uri=True)
    src.row_factory = sqlite3.Row
    src_tables = {
        r[0] for r in src.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }

    target = sa.create_engine(target_url, future=True)
    target_tables = set(sa.inspect(target).get_table_names())

    # Parents first. sorted_tables is a topological sort of the FK graph.
    ordered = [t for t in SQLModel.metadata.sorted_tables if t.name in src_tables]
    skipped = sorted(src_tables - {t.name for t in SQLModel.metadata.sorted_tables})

    if skipped:
        # Not fatal: the old SQLite files predate the current model set.
        print(f"note: {len(skipped)} table(s) in the source are not in the models, skipping:")
        print(f"      {', '.join(skipped)}")

    total = 0
    total_repairs = 0
    for table in ordered:
        if table.name not in target_tables:
            print(f"  !! target has no table '{table.name}' - run migrations first")
            return 3

        rows = src.execute(f'SELECT * FROM "{table.name}"').fetchall()
        count = len(rows)

        payload = [_row_values(r, table) for r in rows]
        repairs = sum(n for _, n in payload)
        values = [v for v, _ in payload]

        if dry_run:
            print(f"  would copy {count:>6} rows into {table.name}"
                  + (f"  ({repairs} NULL->default repairs)" if repairs else ""))
            total += count
            total_repairs += repairs
            continue

        if count:
            with target.begin() as conn:
                conn.execute(table.insert(), values)
        note = f"  ({repairs} NULL->default repairs)" if repairs else ""
        print(f"  copied {count:>6} rows into {table.name}{note}")
        total += count
        total_repairs += repairs

    if total_repairs:
        print(
            f"\n!! {total_repairs} value(s) were NULL in a NOT NULL column and "
            f"were filled from the model default."
        )
        print("   Cause: the old SQLite ADD COLUMN pass dropped NOT NULL.")
        print("   Review with --dry-run before trusting this.")

    if not dry_run:
        with target.begin() as conn:
            _reset_sequences(conn, target)

        # Verify. A silent partial copy is the worst outcome this script has.
        print("\nverifying row counts...")
        bad = 0
        for table in ordered:
            want = src.execute(f'SELECT COUNT(*) FROM "{table.name}"').fetchone()[0]
            with target.connect() as conn:
                got = conn.execute(
                    sa.text(f'SELECT COUNT(*) FROM "{table.name}"')
                ).scalar()
            if want != got:
                print(f"  MISMATCH {table.name}: source={want} target={got}")
                bad += 1
        if bad:
            print(f"\n{bad} table(s) did not match. Treat the target as untrusted.")
            return 1
        print("  all tables match")

    src.close()
    target.dispose()
    print(f"\n{'would copy' if dry_run else 'copied'} {total} rows total")
    return 0


def main(argv: Iterable[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source", default="database/classpilot.db", type=Path)
    ap.add_argument(
        "--target",
        default="postgresql+psycopg://campuspilot:campuspilot@localhost:5432/campuspilot",
        help="SQLAlchemy URL. Must be postgresql+psycopg, not postgresql.",
    )
    ap.add_argument("--dry-run", action="store_true", help="report only, write nothing")
    args = ap.parse_args(argv)
    return migrate(args.source, args.target, args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())