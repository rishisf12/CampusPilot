# Tool access matrix (code-generation reference)

Machine-readable companion to §3 of `ARCHITECTURE.md`. When you implement the
tool layer, this table is the single source of truth for the per-scan
allowlist — do not restate it in prompts.

Legend: `r` = read, `-` = not permitted.

| tool | A_W_HEALTH | B_W_ACTIVITY | C_W_SECURITY | D_W_FEEDBACK | A_A_HEALTH | B_A_ACTIVITY | C_A_SECURITY | D_A_FEEDBACK |
|---|---|---|---|---|---|---|---|---|
| `promql_range` | r | r | r | r | - | - | - | - |
| `promql_instant` | r | r | r | r | - | - | - | - |
| `host_metrics` | r | - | - | - | - | - | - | - |
| `container_metrics` | r | - | - | - | - | - | - | - |
| `db_stats` | r | r | - | r | - | - | - | r |
| `slow_endpoints` | r | - | - | - | - | - | - | - |
| `uptime_status` | r | - | r | - | - | - | - | - |
| `ssl_info` | r | - | r | - | - | - | - | - |
| `log_query` | - | - | r | - | - | - | - | - |
| `auth_failures` | - | - | r | - | - | - | r | - |
| `token_misuse` | - | - | - | - | - | - | r | - |
| `audit_log` | - | - | r | - | - | - | r | - |
| `cve_report` | - | - | r | - | - | - | r | - |
| `event_aggregate` | - | r | - | - | - | r | - | - |
| `revenue_aggregate` | - | r | - | - | - | r | - | - |
| `funnel_aggregate` | - | r | - | - | - | r | - | - |
| `geo_aggregate` | - | r | - | - | - | r | - | - |
| `crash_aggregate` | - | - | - | - | r | - | - | - |
| `anr_aggregate` | - | - | - | - | r | - | - | - |
| `startup_times` | - | - | - | - | r | - | - | - |
| `frame_times` | - | - | - | - | r | - | - | - |
| `api_failure_aggregate` | - | - | - | - | r | - | - | - |
| `battery_memory` | - | - | - | - | r | - | - | - |
| `root_emulator_stats` | - | - | - | - | - | - | r | - |
| `tamper_signals` | - | - | - | - | - | - | r | - |
| `version_breakdown` | - | - | - | - | r | r | r | r |
| `os_breakdown` | - | - | - | - | r | r | - | - |
| `device_breakdown` | - | - | - | - | r | r | - | - |
| `feedback_rows` | - | - | - | r | - | - | - | r |
| `sentiment_aggregate` | - | - | - | r | - | - | - | r |
| `topic_aggregate` | - | - | - | r | - | - | - | r |
| `rating_trend` | - | - | - | r | - | - | - | r |
| `release_markers` | r | r | r | r | r | r | r | r |
| `scan_history` | r | r | r | r | r | r | r | r |

## Enforcement

```python
# obs/allowlist.py
from enum import StrEnum

class Scan(StrEnum):
    A_W_HEALTH = "A_W_HEALTH"
    B_W_ACTIVITY = "B_W_ACTIVITY"
    C_W_SECURITY = "C_W_SECURITY"
    D_W_FEEDBACK = "D_W_FEEDBACK"
    A_A_HEALTH = "A_A_HEALTH"
    B_A_ACTIVITY = "B_A_ACTIVITY"
    C_A_SECURITY = "C_A_SECURITY"
    D_A_FEEDBACK = "D_A_FEEDBACK"


# Deny by default. The set for each scan is the 'r' row above and nothing else.
TOOLS: dict[Scan, frozenset[str]] = {
    Scan.A_W_HEALTH: frozenset({
        "promql_range", "promql_instant", "host_metrics", "container_metrics",
        "db_stats", "slow_endpoints", "uptime_status", "ssl_info",
        "release_markers", "scan_history",
    }),
    Scan.B_W_ACTIVITY: frozenset({
        "promql_instant", "db_stats", "event_aggregate", "revenue_aggregate",
        "funnel_aggregate", "geo_aggregate", "release_markers", "scan_history",
    }),
    Scan.C_W_SECURITY: frozenset({
        "promql_range", "uptime_status", "ssl_info", "auth_failures",
        "audit_log", "cve_report", "log_query",
        "release_markers", "scan_history",
    }),
    Scan.D_W_FEEDBACK: frozenset({
        "feedback_rows", "sentiment_aggregate", "topic_aggregate",
        "rating_trend", "db_stats",
        "release_markers", "scan_history",
    }),
    Scan.A_A_HEALTH: frozenset({
        "crash_aggregate", "anr_aggregate", "startup_times", "frame_times",
        "api_failure_aggregate", "battery_memory", "version_breakdown",
        "os_breakdown", "device_breakdown",
        "release_markers", "scan_history",
    }),
    Scan.B_A_ACTIVITY: frozenset({
        "event_aggregate", "revenue_aggregate", "funnel_aggregate",
        "geo_aggregate", "version_breakdown", "os_breakdown", "device_breakdown",
        "release_markers", "scan_history",
    }),
    Scan.C_A_SECURITY: frozenset({
        "root_emulator_stats", "tamper_signals", "auth_failures", "token_misuse",
        "version_breakdown", "audit_log", "cve_report",
        "release_markers", "scan_history",
    }),
    Scan.D_A_FEEDBACK: frozenset({
        "feedback_rows", "sentiment_aggregate", "topic_aggregate",
        "rating_trend", "version_breakdown",
        "release_markers", "scan_history",
    }),
}


def permits(scan: Scan, tool: str) -> bool:
    """Server-side check. Called before every tool dispatch.

    This is the layer that matters. Prompt wording ("you may only use X") is a
    suggestion the model can be talked out of; this is a dict lookup.
    """
    return tool in TOOLS[scan]
```

## Invariants worth asserting in tests

1. `TOOLS[scan]` is never empty, and no scan contains a write tool
   (`sqlite_write`, `db_exec`, `fs_write`, `shell`, `http_post`).
2. No web scan contains an Android tool and vice versa.
3. `release_markers` and `scan_history` are in all eight sets.
4. A tool present in `opencode.json`'s agent block but absent here is rejected —
   config drift fails closed.

Test 4 is the one that will save you: it catches the case where someone adds a
tool to the agent config during debugging and forgets to add it here.

```python
def test_opencode_config_matches_allowlist() -> None:
    """Fail closed: an unlisted tool in the agent config must be an error."""
    cfg = json.loads(Path("docs/observability/opencode.json").read_text())
    for agent_name, agent in cfg["agent"].items():
        m = re.fullmatch(r"scan-(web|android)-(health|activity|security|feedback)",
                         agent_name)
        if not m:
            continue
        platform = {"web": "W", "android": "A"}[m[1]]
        section = {"health": "HEALTH", "activity": "ACTIVITY",
                   "security": "SECURITY", "feedback": "FEEDBACK"}[m[2]]
        scan = Scan(f"{section[0]}_{platform}_{section}")
        for tool, enabled in agent["tools"].items():
            if tool in ("bash", "write", "edit", "webfetch"):
                assert enabled is False, f"{agent_name} enables {tool}"
            elif enabled:
                assert permits(scan, tool), (
                    f"{agent_name} enables {tool!r} but the allowlist forbids it"
                )
```

Note the agent-name convention this test assumes — it also pins the
subsection↔agent mapping, so renaming an agent in `opencode.json` without
updating `Scan` is a test failure rather than a silently-dead scan.