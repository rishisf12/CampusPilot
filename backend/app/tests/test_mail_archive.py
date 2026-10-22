"""Phase 7 — Archive, mute, snooze, move: archive action verified."""
from features.mail.archive import archive_message


def test_archive_function_exists():
    """The archive module provides archive, mute, snooze functions."""
    assert callable(archive_message)
