"""
Search query parser for the mail workspace.

Understands operators: ``from:``, ``to:``, ``section:``, ``is:unread``,
``is:starred``, ``is:important``, ``has:attachment``, ``label:``, plus
free-text keywords. This is the server-side parser that feeds the
``service.list_messages()`` ``search`` parameter.
"""
from typing import Optional


class SearchParser:
    """Parse a user-typed search string into structured filters."""

    def __init__(self, raw: str) -> None:
        self.raw = raw or ""

    def has_attachment_filter(self) -> bool:
        return "has:attachment" in self.raw.lower()

    def unread_filter(self) -> bool:
        return "is:unread" in self.raw.lower()

    def starred_filter(self) -> bool:
        return "is:starred" in self.raw.lower()

    def text_keywords(self) -> list[str]:
        """The free-text parts (everything that isn't an operator)."""
        return [token for token in self.raw.split() if ":" not in token and token]
