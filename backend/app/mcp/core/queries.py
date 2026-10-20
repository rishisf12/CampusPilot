"""Query guard for MCP tools that take SQL text.

Implements SCAN-AGENT.md rules 4 and 5 — the table allowlist and the read-only
rule — as string checks *before* anything reaches the engine. A refused query
never touches Postgres; the refusal is what the audit log records.
"""
from __future__ import annotations

import re
from mcp.core.registry import ToolNotPermitted

#: Statement kinds a scan may never run. Word-boundary match, so a column named
#: `last_update` does not trip the `UPDATE` rule and `last_created` not `CREATE`.
_WRITE_RE = re.compile(
    r"\b(insert|update|delete|drop|alter|create|truncate|grant|revoke|vacuum)\b",
    re.IGNORECASE,
)

#: Credential-adjacent tables (SCAN-AGENT.md rule 4): a scan may only ever read
#: them as an error message. Plain substrings — schema-prefixed names still match.
_FORBIDDEN_REFERENCES = ("auth_", "token", "password_hash")

#: Max SQL length before the check even looks at content (rule 5).
MAX_SQL_LENGTH = 20_000


def assert_read_query(sql: str) -> str:
    """
    Return the SQL unchanged if it is provably read-only and non-credential;
    raise `ToolNotPermitted` otherwise.
    """
    if not sql or not sql.strip():
        raise ToolNotPermitted("empty query")
    if len(sql) > MAX_SQL_LENGTH:
        raise ToolNotPermitted(f"query exceeds {MAX_SQL_LENGTH} characters")
    match = _WRITE_RE.search(sql)
    if match:
        raise ToolNotPermitted(f"query contains write keyword {match.group(1)!r}")
    lowered = sql.lower()
    for ref in _FORBIDDEN_REFERENCES:
        if ref in lowered:
            raise ToolNotPermitted(
                f"query references protected table fragment {ref!r}"
            )
    return sql
