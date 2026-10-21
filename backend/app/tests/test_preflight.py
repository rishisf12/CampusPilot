"""Tests for the preflight gate (Phase 8).

The gate is only worth having if it keeps telling the truth, so the checks
themselves are tested: the static ones must pass on this repository, and a
deliberately broken configuration must make the relevant check fail.

The database-backed checks are not exercised here - they need a live
Postgres and a scan, which the suite itself provides elsewhere. What matters
is that the static checks are wired to the real files, not to a copy.
"""
import importlib.util
import pathlib

import pytest


REPO = pathlib.Path(__file__).resolve().parents[3]
SCRIPT = REPO / "scripts" / "preflight.py"


def _load():
    spec = importlib.util.spec_from_file_location("preflight", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def preflight():
    assert SCRIPT.exists(), f"the preflight script is missing: {SCRIPT}"
    return _load()


def test_the_script_exists_and_answers(preflight):
    assert preflight.REPO_ROOT == REPO
    assert len(preflight.CHECKS) == 10


def test_the_local_model_provider_check_passes_and_catches_a_regression(
    preflight, tmp_path, monkeypatch
):
    """No local model provider, and the check says so if one comes back."""
    result = preflight.check_no_local_model_provider()
    assert result.status == preflight.PASS

    compose = tmp_path / "docker-compose.yml"
    compose.write_text(
        "services:\n  backend:\n    environment:\n      - OLLAMA_BASE_URL=http://ollama:11434/v1\n",
        encoding="utf-8",
    )
    env_example = tmp_path / ".env.example"
    env_example.write_text("OLLAMA_BASE_URL=http://ollama:11434/v1\n", encoding="utf-8")
    monkeypatch.setattr(preflight, "COMPOSE", compose)
    monkeypatch.setattr(preflight, "ENV_EXAMPLE", env_example)
    failed = preflight.check_no_local_model_provider()
    assert failed.status == preflight.FAIL
    assert "local model provider" in failed.detail


def test_the_static_checks_pass_on_this_repository(preflight):
    for check in (
        preflight.check_no_shell_mcp_in_prod_config,
        preflight.check_admin_mcp_off_by_default,
        preflight.check_no_app_secrets_in_other_services,
        preflight.check_monitoring_stack_removed,
    ):
        result = check()
        assert result.status == preflight.PASS, f"{result.name}: {result.detail}"


def test_a_shell_mcp_in_the_compose_config_fails_the_check(preflight, tmp_path, monkeypatch):
    compose = tmp_path / "docker-compose.yml"
    compose.write_text(
        "services:\n"
        "  agent:\n"
        "    image: agent:latest\n"
        "    volumes:\n"
        "      - ./.opencode:/app/.opencode\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(preflight, "COMPOSE", compose)
    result = preflight.check_no_shell_mcp_in_prod_config()
    assert result.status == preflight.FAIL
    assert ".opencode" in result.detail


def test_the_admin_mcp_switched_on_fails_the_check(preflight, tmp_path, monkeypatch):
    compose = tmp_path / "docker-compose.yml"
    compose.write_text(
        "services:\n"
        "  backend:\n"
        "    environment:\n"
        "      - ENABLE_ADMIN_MCP=true\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(preflight, "COMPOSE", compose)
    monkeypatch.setattr(preflight, "ENV_EXAMPLE", tmp_path / "missing.env")
    result = preflight.check_admin_mcp_off_by_default()
    assert result.status == preflight.FAIL


def test_a_secret_outside_the_backend_fails_the_check(preflight, tmp_path, monkeypatch):
    compose = tmp_path / "docker-compose.yml"
    compose.write_text(
        "services:\n"
        "  backend:\n"
        "    environment:\n"
        "      - SECRET_KEY=x\n"
        "  agent:\n"
        "    environment:\n"
        "      - SECRET_KEY=x\n"
        "      - SMTP_PASSWORD=y\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(preflight, "COMPOSE", compose)
    result = preflight.check_no_app_secrets_in_other_services()
    assert result.status == preflight.FAIL
    assert "agent" in result.detail


def test_a_monitoring_container_left_behind_fails_the_check(preflight, tmp_path, monkeypatch):
    """The containers were removed; one coming back is a failure."""
    compose = tmp_path / "docker-compose.yml"
    compose.write_text(
        "services:\n"
        "  grafana:\n"
        "    image: grafana/grafana:11.1.0\n"
        "    networks:\n"
        "      - edge\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(preflight, "COMPOSE", compose)
    result = preflight.check_monitoring_stack_removed()
    assert result.status == preflight.FAIL
    assert "grafana" in result.detail


def test_a_monitoring_volume_left_behind_fails_the_check(preflight, tmp_path, monkeypatch):
    compose = tmp_path / "docker-compose.yml"
    compose.write_text(
        "services:\n  backend:\n    image: backend\n"
        "volumes:\n  grafana_data:\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(preflight, "COMPOSE", compose)
    result = preflight.check_monitoring_stack_removed()
    assert result.status == preflight.FAIL
    assert "grafana_data" in result.detail


def test_the_preflight_exits_zero_when_everything_passes(preflight, monkeypatch, capsys):
    # Only the static checks: the database-backed ones need a live database,
    # and the suite provides that elsewhere.
    monkeypatch.setattr(
        preflight,
        "CHECKS",
        (
            preflight.check_no_shell_mcp_in_prod_config,
            preflight.check_admin_mcp_off_by_default,
            preflight.check_no_app_secrets_in_other_services,
            preflight.check_monitoring_stack_removed,
        ),
    )
    code = preflight.main([])
    assert code == 0
    out = capsys.readouterr().out
    assert "0 failed" in out
