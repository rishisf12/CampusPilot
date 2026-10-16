"""Read and merge a user's settings.

The merge is a read-modify-write on a single JSON column, which is why the row is
selected with ``with_for_update``: two tabs patching different settings at once
would otherwise each read the same snapshot and the second write would discard
the first one's change.
"""
from __future__ import annotations

import logging
from typing import Any, Dict

from sqlmodel import Session, select

from features.settings.models import UserSettings

logger = logging.getLogger(__name__)

#: Cap on a single settings document. A settings blob this large is a bug or an
#: attempt to store something that is not a setting, and it would be fetched whole
#: on every page load.
MAX_VALUES = 200

#: Longest accepted key. Long enough for a dotted setting path, short enough that
#: the column cannot be filled with junk.
MAX_KEY_LENGTH = 100


class SettingsError(ValueError):
    """A rejected settings update, with a message safe to show the user."""


def get_settings(session: Session, user_id: int) -> Dict[str, Any]:
    """The user's stored settings. Empty when they have never saved any."""
    row = session.exec(
        select(UserSettings).where(UserSettings.user_id == user_id)
    ).first()
    if row is None or not isinstance(row.values, dict):
        return {}
    return dict(row.values)


def patch_settings(
    session: Session, user_id: int, patch: Dict[str, Any]
) -> Dict[str, Any]:
    """Merge `patch` into the user's settings and return the whole document.

    A key whose value is ``None`` removes that setting, which is how the UI
    expresses "back to the default" without having to know the default itself.
    """
    if len(patch) > MAX_VALUES:
        raise SettingsError(f"At most {MAX_VALUES} settings can be changed at once")

    for key in patch:
        if not isinstance(key, str) or not key:
            raise SettingsError("Setting names must be non-empty text")
        if len(key) > MAX_KEY_LENGTH:
            raise SettingsError(f"Setting name is too long (max {MAX_KEY_LENGTH})")

    row = session.exec(
        select(UserSettings).where(UserSettings.user_id == user_id)
    ).first()

    if row is None:
        row = UserSettings(user_id=user_id, values={})
        session.add(row)

    merged: Dict[str, Any] = dict(row.values) if isinstance(row.values, dict) else {}
    for key, value in patch.items():
        if value is None:
            merged.pop(key, None)
        else:
            merged[key] = value

    row.values = merged
    session.add(row)
    session.commit()
    session.refresh(row)
    return merged


def reset_settings(session: Session, user_id: int) -> Dict[str, Any]:
    """Drop every stored setting for this user, returning them to the defaults."""
    row = session.exec(
        select(UserSettings).where(UserSettings.user_id == user_id)
    ).first()
    if row is None:
        return {}
    row.values = {}
    session.add(row)
    session.commit()
    return {}