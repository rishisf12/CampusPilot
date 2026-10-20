"""In-house observability (see `docs/MCP_MIGRATION_PLAN.md`, bundle rule 7).

The collectors that used to be separate containers, now owned by the API
process:

- `host`  — CPU / RAM / disk / network from psutil (replaces node-exporter
  and cAdvisor; parity rows 1 of Phase 6's checklist).
- `uptime` — availability derived at *read* time from `health_metric`
  sample coverage (replaces blackbox-exporter; parity row 8).

Both are libraries, not daemons: no sockets to expose, nothing to scrape,
one less thing to keep alive. `features.monitoring.infrastructure.health`
remains the only writer of `health_metric` and consumes both.
"""
