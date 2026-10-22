"""Phase 8 — Settings & hardening: admin settings module verified."""
from features.mail.admin_settings import AdminMailSettingsCreate


def test_admin_settings_model_exists():
    s = AdminMailSettingsCreate(provider="dummy")
    assert s.provider == "dummy"
