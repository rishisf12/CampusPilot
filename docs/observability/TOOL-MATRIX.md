# Tool access matrix (code-generation reference)

The single source of truth for the per-scan allowlist: which tool a scan
subsection may call. **The registry is the authority** — this table is
generated from it, so it cannot drift:

```bash
cd backend/app && python -c "
from mcp.core.registry import SUBSECTIONS
from mcp.monitoring import REGISTRY
for name in REGISTRY.names():
    spec, _ = REGISTRY.resolve(name)
    print(name, sorted(spec.subsections))
"
```

Legend: `r` = read, `-` = not permitted. A call outside the row is refused
server-side, before the tool runs, and the refusal is audited.

| tool | A_W_HEALTH | B_W_ACTIVITY | C_W_SECURITY | D_W_FEEDBACK | A_A_HEALTH | B_A_ACTIVITY | C_A_SECURITY | D_A_FEEDBACK |
|---|---|---|---|---|---|---|---|---|
| `alert_channels` | - | - | r | - | - | - | - | - |
| `alert_rules` | r | - | r | - | r | - | - | - |
| `alert_summary` | r | - | r | - | r | - | - | - |
| `crash_clusters` | - | - | - | - | r | - | - | r |
| `daily_active_users` | - | r | - | - | - | r | - | - |
| `failed_logins_by_hour` | - | - | r | - | - | - | r | - |
| `feedback_themes_top5` | - | - | - | r | - | - | - | r |
| `health_latest` | r | - | - | - | - | - | - | - |
| `health_uptime_pct` | r | - | - | - | - | - | - | - |
| `open_alerts` | r | - | r | - | r | - | - | - |
| `p95_latency_window` | r | - | - | - | r | - | - | - |
| `security_signals` | - | - | r | - | - | - | r | - |
| `telemetry_health` | r | - | - | - | r | - | - | - |

Two rules apply to every tool in the table, not just to the ones in a row:

- **read-only** — no tool writes, and no tool can act on a finding. The
  reactor (propose, never execute) is a separate component with its own
  contract;
- **redacted** — every answer passes the egress gate before it reaches the
  model, so a raw row never enters the context. See
  `docs/observability/SCAN-AGENT.md` §4 rule 8.

The tools that used to be in this table — `promql_range`, `host_metrics`,
`db_stats`, `log_query` and the rest of the Prometheus-era set — are gone
with the containers they read. Their replacements read the app's own stores:
`observability.host` (psutil) for the host figures,
`observability.uptime` for the uptime, and the aggregate tools above for
everything else.
