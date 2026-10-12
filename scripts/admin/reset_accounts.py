"""Delete every student account so a fresh signup is possible.

Signup rejects a duplicate username or email. Test runs leave accounts behind that
were never real students, and once one of those names is taken it cannot be
registered again - so clearing the account table is the fix.

**Academic data is not touched.** The timetable, courses, exam seating and the
uploaded PDFs live in the same file and are the expensive part; losing them would
mean re-uploading every document. Only sign-in data is removed:

    user, user_profile, passkey_credential, password_reset_code

A timestamped backup is written first. The database is gitignored, so without one
this would be irreversible.

Usage:
    python tools/reset_accounts.py --yes          # delete all accounts
    python tools/reset_accounts.py --yes --keep testuser123
"""
import os
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DB = REPO / "database" / "classpilot.db"

#: Only sign-in data. Timetable, exams, courses and uploads are deliberately
#: absent - see the module docstring.
ACCOUNT_TABLES = [
    "password_reset_code",
    "passkey_credential",
    "user_profile",
    "user",
]


def refuse_if_not_local() -> bool:
    """A real deployment uses DATABASE_URL; this tool must not touch that."""
    if os.environ.get("DATABASE_URL"):
        print("DATABASE_URL is set - refusing to edit the file database.")
        print("Run this only against a local development database.")
        return True
    if DB.suffix != ".db" or not DB.is_file():
        print(f"refusing to touch {DB}")
        return True
    return False


def back_up() -> Path:
    """
    Copy the database aside, so a mistake here is recoverable.

    Must be called before anything is deleted. The app holds the database open
    for the life of the process, so the copy is taken of the file on disk while
    the connection is still idle; that is consistent because nothing has been
    written yet.
    """
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    target = DB.with_name(f"classpilot.backup-{stamp}.db")
    shutil.copy2(DB, target)

    # A backup that cannot be opened is not a backup.
    check = sqlite3.connect(target)
    if check.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
        check.close()
        target.unlink()
        raise RuntimeError("backup failed its integrity check; refusing to delete anything")
    users = check.execute("SELECT COUNT(*) FROM user").fetchone()[0]
    check.close()

    print(f"backup verified: {users} account(s) recorded in {target.name}")
    return target


def main() -> int:
    if refuse_if_not_local():
        return 1

    if "--yes" not in sys.argv:
        print(__doc__)
        print("Nothing was changed. Re-run with --yes to actually delete.")
        return 1

    keep = set()
    if "--keep" in sys.argv:
        index = sys.argv.index("--keep")
        keep = {name.strip() for name in sys.argv[index + 1].split(",") if name.strip()}

    conn = sqlite3.connect(DB)
    doomed_ids = []
    doomed = []
    for user_id, username in conn.execute("SELECT id, username FROM user ORDER BY id"):
        if username not in keep:
            doomed_ids.append(user_id)
            doomed.append(username)

    if not doomed:
        print(f"Nothing to delete (kept: {', '.join(keep) or 'nothing kept'}).")
        return 0

    print(f"deleting {len(doomed)} account(s): {', '.join(doomed)}")
    if keep:
        print(f"keeping: {', '.join(keep)}")

    # The backup must be taken BEFORE the delete, or it only records the damage.
    saved_file = back_up()
    print(f"backup written first: {saved_file.name}")

    with conn:
        for table in ACCOUNT_TABLES:
            # Profile rows hang off user_id, so they go with their account.
            if table == "user_profile":
                for user_id in doomed_ids:
                    conn.execute("DELETE FROM user_profile WHERE user_id = ?", (user_id,))
            else:
                conn.execute(f"DELETE FROM {table}")

    print("\nremoved:")
    for table in ACCOUNT_TABLES:
        count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"  {table:<24} {count:>6} rows")

    untouched = ["timetable_slot", "course", "exam_seating", "mid_sem_schedule",
                 "exam_upload", "timetable_upload"]
    print("\nkept (academic data):")
    for table in untouched:
        try:
            count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        except sqlite3.OperationalError:
            continue
        print(f"  {table:<24} {count:>6} rows")

    conn.close()

    print("\nsign-up should now accept a new account.")
    print(f"to undo: copy {saved_file.name} over {DB.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
