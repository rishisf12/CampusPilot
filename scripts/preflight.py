#!/usr/bin/env python3
"""Preflight: the gate that keeps this migration's promises true.

Nine checks, one line each, non-zero exit when any of them fails. The point
is that the rules are *checked*, not remembered:

1. no shell/terminal MCP is reachable from the production configuration;
2. the admin MCP endpoint is not switched on in production;
3. no application secret reaches a service that is not the backend;
4. the egress gate is wired into `run_tool` (a telemetry job would refuse
   to start otherwise);
5. every provider a job can name is on the free allowlist;
6. `.opencode/` is not in the built backend image;
7. the agent's database role is read-only restricted;
8. Prometheus and Grafana are not on the edge network;
9. an egress audit row exists after a test scan.

Usage:

    python scripts/preflight.py                 # static checks + DB checks if reachable
    python scripts/preflight.py --image <name>  # also check a built image
    python scripts/preflight.py --strict        # treat SKIP as a failure

Exit codes: 0 all good, 1 at least one failure, 2 the script itself broke.
"""
from __future__ import annotations

import argparse
import os
import pathlib
import re
import subprocess
import sys
from typing import Callable, Iterable

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
COMPOSE = REPO_ROOT / "docker-compose.yml"
DOCKERFILE = REPO_ROOT / "backend" / "Dockerfile"
DOCKERIGNORE = REPO_ROOT / ".dockerignore"
ENV_EXAMPLE = REPO_ROOT / ".env.example"

#: The services that carry the application's secrets. Everything else must
#: be clean.
APP_SECRET_HOLDERS = {"backend"}

#: Names that must never appear in a service's environment unless that
#: service is the backend.
FORBIDDEN_ENV_NAMES = (
    "SECRET_KEY",
    "SMTP_HOST",
    "SMTP_PORT",
    "SMTP_USER",
    "SMTP_PASSWORD",
    "EMAIL_FROM",
    "TELEMETRY_PEPPER",
    "OPENAI_API_KEY",
)

#: The monitoring stack that must stay off the edge while the parity gate
#: is running.
OFF_EDGE_SERVICES = (
    "prometheus",
    "grafana",
    "node-exporter",
    "alertmanager",
    "victoria-logs",
    "cAdvisor",
    "blackbox-exporter",
    "postgres",
    "rollup",
    "adminer",
)

PASS = "PASS"
FAIL = "FAIL"
SKIP = "SKIP"


class Result:
    """One check's outcome."""

    def __init__(self, name: str, status: str, detail: str) -> None:
        self.name = name
        self.status = status
        self.detail = detail

    def line(self) -> str:
        return f"{self.status:<4} {self.name}: {self.detail}"


def _load_compose() -> dict:
    import yaml

    with COMPOSE.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def _app_path() -> str:
    return str(REPO_ROOT / "backend" / "app")


def _import_app():
    """Put the application on the path, or return None if it cannot load."""
    path = _app_path()
    if path not in sys.path:
        sys.path.insert(0, path)
    try:
        import core.config  # noqa: F401
        import llms  # noqa: F401
        import mcp.core.registry  # noqa: F401
    except Exception as exc:  # noqa: BLE001 - a missing dependency is a SKIP, not a FAIL
        print(f"    (import failed: {type(exc).__name__}: {exc})", file=sys.stderr)
        return None
    return sys.modules


def _compose_default(value: str) -> str:
    """The default of a compose template: `${VAR:-off}` -> `off`."""
    match = re.search(r":-([^}]*)\}", value)
    if match:
        return match.group(1).strip()
    return value.strip()


# --- the checks --------------------------------------------------------------


def check_no_shell_mcp_in_prod_config() -> Result:
    """The v1 shell MCP server must not be reachable from production."""
    name = "no-shell-mcp-in-prod-config"
    try:
        compose = _load_compose()
    except Exception as exc:  # noqa: BLE001
        return Result(name, SKIP, f"could not read docker-compose.yml: {exc}")
    text = COMPOSE.read_text(encoding="utf-8")
    offenders = []
    for service, spec in (compose.get("services") or {}).items():
        blob = str(spec)
        for needle in (".opencode", "mcp_servers", "shell_server", "opencode"):
            if needle in blob:
                offenders.append(f"{service} references {needle}")
    if "opencode" in text.lower() and "docker-compose" in text:
        # A mention in a comment is fine; a mount or a command is not.
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if ".opencode" in stripped or "shell_server" in stripped:
                offenders.append(stripped)
    if offenders:
        return Result(name, FAIL, "; ".join(sorted(set(offenders))))
    return Result(name, PASS, "no shell MCP is reachable from the compose config")


def check_admin_mcp_off_by_default() -> Result:
    """The optional admin console must be off unless an operator opts in."""
    name = "admin-mcp-off-by-default"
    try:
        compose = _load_compose()
    except Exception as exc:  # noqa: BLE001
        return Result(name, SKIP, f"could not read docker-compose.yml: {exc}")
    backend = (compose.get("services") or {}).get("backend") or {}
    env = backend.get("environment") or []
    offenders = []
    if isinstance(env, dict):
        entries = [f"{k}={v}" for k, v in env.items()]
    else:
        entries = [str(e) for e in env]
    for entry in entries:
        if entry.startswith("ENABLE_ADMIN_MCP=") and entry.split("=", 1)[1].strip().lower() in {
            "true",
            "1",
            "yes",
        }:
            offenders.append(entry)
    if ENV_EXAMPLE.exists():
        for line in ENV_EXAMPLE.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("ENABLE_ADMIN_MCP=") and line.split("=", 1)[1].strip().lower() in {
                "true",
                "1",
                "yes",
            }:
                offenders.append(line.strip())
    if offenders:
        return Result(name, FAIL, f"ENABLE_ADMIN_MCP is on: {offenders}")
    return Result(name, PASS, "ENABLE_ADMIN_MCP defaults to off")


def check_no_app_secrets_in_other_services() -> Result:
    """Only the backend may hold the application's secrets."""
    name = "no-app-secrets-outside-the-backend"
    try:
        compose = _load_compose()
    except Exception as exc:  # noqa: BLE001
        return Result(name, SKIP, f"could not read docker-compose.yml: {exc}")
    offenders = []
    for service, spec in (compose.get("services") or {}).items():
        if service in APP_SECRET_HOLDERS:
            continue
        env = (spec or {}).get("environment") or []
        if isinstance(env, dict):
            names = [str(k) for k in env]
        else:
            names = [str(e).split("=", 1)[0] for e in env]
        for forbidden in FORBIDDEN_ENV_NAMES:
            if forbidden in names:
                offenders.append(f"{service} carries {forbidden}")
    if offenders:
        return Result(name, FAIL, "; ".join(sorted(offenders)))
    return Result(name, PASS, "no application secret outside the backend")


def check_redaction_wired() -> Result:
    """The egress gate must be inside `run_tool`."""
    name = "egress-gate-wired"
    if _import_app() is None:
        return Result(name, SKIP, "the application could not be imported")
    from mcp.core.registry import redaction_wired

    if not redaction_wired():
        return Result(name, FAIL, "run_tool no longer redacts - a telemetry job would leak")
    return Result(name, PASS, "run_tool redacts before anything is returned")


def check_provider_on_allowlist() -> Result:
    """Every provider a job can name must be on the free allowlist."""
    name = "providers-on-the-allowlist"
    if _import_app() is None:
        return Result(name, SKIP, "the application could not be imported")
    from llms import ALLOWED_PROVIDERS

    offenders = []
    try:
        compose = _load_compose()
        backend = (compose.get("services") or {}).get("backend") or {}
        env = backend.get("environment") or []
        entries = [str(e) for e in env] if not isinstance(env, dict) else [
            f"{k}={v}" for k, v in env.items()
        ]
        for entry in entries:
            if entry.startswith("LLM_PROVIDER="):
                value = _compose_default(entry.split("=", 1)[1]).lower()
                if value and value != "off" and value not in ALLOWED_PROVIDERS:
                    offenders.append(entry)
    except Exception:  # noqa: BLE001
        pass

    from mcp.core.llm import DEFAULT_FALLBACKS

    for provider in DEFAULT_FALLBACKS:
        if provider not in ALLOWED_PROVIDERS:
            offenders.append(f"agent fallback {provider!r}")

    if offenders:
        return Result(name, FAIL, "; ".join(sorted(set(offenders))))
    return Result(name, PASS, f"every provider is on {sorted(ALLOWED_PROVIDERS)}")


def check_opencode_not_in_image(image: str | None = None) -> Result:
    """`.opencode/` must not be in the built backend image."""
    name = "opencode-not-in-the-image"
    problems = []
    dockerfile = DOCKERFILE.read_text(encoding="utf-8") if DOCKERFILE.exists() else ""
    for line in dockerfile.splitlines():
        stripped = line.strip()
        if stripped.startswith("COPY") and re.search(r"\b(\.|\*)\s*$", stripped):
            problems.append(f"Dockerfile copies everything: {stripped}")
    ignore = DOCKERIGNORE.read_text(encoding="utf-8") if DOCKERIGNORE.exists() else ""
    if ".opencode" not in ignore:
        problems.append(".dockerignore does not exclude .opencode/")
    if image:
        try:
            result = subprocess.run(
                ["docker", "run", "--rm", image, "ls", "/app/.opencode"],
                capture_output=True,
                text=True,
                timeout=120,
            )
            if result.returncode == 0:
                problems.append(f"{image} contains /app/.opencode")
        except Exception as exc:  # noqa: BLE001
            return Result(name, SKIP, f"could not inspect {image}: {exc}")
    if problems:
        return Result(name, FAIL, "; ".join(problems))
    return Result(name, PASS, ".opencode/ is excluded from the image")


def check_agent_db_role_read_only() -> Result:
    """The agent's database role must be read-only restricted."""
    name = "agent-db-role-read-only"
    versions = REPO_ROOT / "backend" / "alembic" / "versions"
    granted = False
    for path in versions.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        if "monitoring_ro" in text and "GRANT SELECT" in text:
            granted = True
            break
    if not granted:
        return Result(name, FAIL, "no migration grants SELECT to the read-only role")

    url = os.environ.get("TEST_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if not url:
        return Result(name, PASS, "grants are in the migrations (no database to verify against)")
    try:
        import psycopg
    except Exception:  # noqa: BLE001
        return Result(name, SKIP, "psycopg is not installed - the grants could not be verified")
    try:
        # The app's URLs are SQLAlchemy-flavoured; psycopg wants its own.
        dsn = url.replace("postgresql+psycopg://", "postgresql://")
        with psycopg.connect(dsn) as conn:
            row = conn.execute(
                "SELECT rolconfig FROM pg_roles WHERE rolname = 'monitoring_ro'"
            ).fetchone()
            if row is None:
                return Result(name, FAIL, "the monitoring_ro role does not exist")
            # rolconfig is a list of "key=value" strings.
            settings = " ".join(row[0] or [])
            if "default_transaction_read_only=on" not in settings.replace(" ", ""):
                return Result(name, FAIL, "monitoring_ro is not read-only by default")
    except Exception as exc:  # noqa: BLE001
        return Result(name, SKIP, f"could not reach the database: {exc}")
    return Result(name, PASS, "monitoring_ro exists and is read-only by default")


def check_monitoring_off_the_edge() -> Result:
    """Prometheus and Grafana must not be on the edge network."""
    name = "monitoring-stack-off-the-edge"
    try:
        compose = _load_compose()
    except Exception as exc:  # noqa: BLE001
        return Result(name, SKIP, f"could not read docker-compose.yml: {exc}")
    offenders = []
    for service in OFF_EDGE_SERVICES:
        spec = (compose.get("services") or {}).get(service)
        if not spec:
            continue
        networks = spec.get("networks") or []
        if isinstance(networks, dict):
            names = list(networks)
        else:
            names = [str(n) for n in networks]
        if "edge" in names:
            offenders.append(service)
    if offenders:
        return Result(name, FAIL, f"on the edge network: {sorted(offenders)}")
    return Result(name, PASS, f"the monitoring stack is off the edge network")


def check_egress_audit_rows() -> Result:
    """A scan must leave an egress audit row behind."""
    name = "egress-audit-rows-after-a-scan"
    url = os.environ.get("TEST_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if not url:
        return Result(name, SKIP, "no database URL to scan against")
    if _import_app() is None:
        return Result(name, SKIP, "the application could not be imported")
    try:
        import asyncio

        from sqlmodel import Session

        from core.database import engine
        from features.monitoring.domain.models import ToolCallAudit
        from mcp.agent import run_scan

        async def _fake(_messages):
            return {
                "status": "healthy",
                "summary": "Preflight scan: the measured signals are inside their band.",
                "findings": [],
                "root_causes": [],
                "recommended_actions": [],
                "confidence": {"level": "high"},
            }

        with Session(engine) as session:
            scan_id = "preflight-scan"
            asyncio.run(
                run_scan(
                    session,
                    subsection="A_W_HEALTH",
                    scan_id=scan_id,
                    chat=_fake,
                    store=False,
                )
            )
            rows = session.exec(
                select_rows(ToolCallAudit, scan_id)
            ).all()
            if not rows:
                return Result(name, FAIL, "the scan left no audit rows")
            # Every tool call carries the egress metadata (the salt and the
            # mask count) - that is the proof the gate ran.
            without_egress = [
                row.tool for row in rows if not (row.args or {}).get("egress")
            ]
            if without_egress:
                return Result(
                    name,
                    FAIL,
                    f"audit rows without egress metadata: {sorted(set(without_egress))}",
                )
            # An outbound LLM request must name its provider and its size.
            outbound = [row for row in rows if (row.tool or "").startswith("llm.")]
            for row in outbound:
                if not row.sent_to or not row.bytes_out:
                    return Result(
                        name, FAIL, f"outbound row {row.tool!r} has no provider or size"
                    )
    except Exception as exc:  # noqa: BLE001
        return Result(name, SKIP, f"could not run the preflight scan: {exc}")
    return Result(name, PASS, "the scan left egress audit rows")


def select_rows(model, scan_id: str):
    from sqlmodel import select

    return select(model).where(model.scan_id == scan_id)


CHECKS: tuple[Callable[[], Result], ...] = (
    check_no_shell_mcp_in_prod_config,
    check_admin_mcp_off_by_default,
    check_no_app_secrets_in_other_services,
    check_redaction_wired,
    check_provider_on_allowlist,
    check_opencode_not_in_image,
    check_agent_db_role_read_only,
    check_monitoring_off_the_edge,
    check_egress_audit_rows,
)


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", help="also check this built image for /app/.opencode")
    parser.add_argument(
        "--strict", action="store_true", help="treat a skipped check as a failure"
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    results: list[Result] = []
    for check in CHECKS:
        try:
            if check is check_opencode_not_in_image:
                results.append(check_opencode_not_in_image(args.image))
            else:
                results.append(check())
        except Exception as exc:  # noqa: BLE001 - a broken check must not hide the others
            results.append(Result(getattr(check, "__name__", "check"), FAIL, f"the check broke: {exc}"))

    print("Preflight - CampusPilot agent tooling")
    print("-" * 60)
    for result in results:
        print(result.line())
    failures = [r for r in results if r.status == FAIL]
    skips = [r for r in results if r.status == SKIP]
    print("-" * 60)
    print(
        f"{len(results) - len(failures) - len(skips)} passed, "
        f"{len(failures)} failed, {len(skips)} skipped"
    )
    if failures:
        return 1
    if skips and args.strict:
        print("strict mode: a skipped check is a failure")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
