# MCP Migration & Expansion Plan

> Status: PLANNED — not started. Nothing in this document removes existing
> infrastructure until the MCP pipeline achieves verified parity.
>
> Governing directives (from the owner):
> 1. Remove files phase-wise, only when the same work is achieved and verified by our own MCP.
> 2. Plan a proper bundled directory tree for backend and frontend; changing existing
>    features to make them more advanced is in scope; MCP hosting = minimal storage.
> 3. Execute in phases; verify progress in each; fix all bugs before a phase closes.
> 4. Add/modify as many features as sensible and LIST ALL; progress bars monitor
>    security and everything else; the app must not become bulky; everything must fit
>    free deployment.
> 5. Admin powered by AI: finds bugs, security threats, malware attacks, etc.; clean,
>    organised UI — no messy UI, no long horizontal/vertical scrolling, properly bundled.
> 6. Build and use our own working MCPs for everything, integrated with AI; use what is
>    available now (more will be set up if needed); prefer open-source used directly.
>    NEVER use anything paid or that needs payment after deployment. Free forever or not shipped.
> 7. Dedicated bundle per MCP; a clearly named LLM section mapping which LLM file
>    integrates with which feature; separate bundles for future maintenance.

---

## 0. Baseline inventory (verified 2026-10-20, read-only audit)

### What the current monitoring stack runs (docker-compose.yml)

| # | Service | Image | Role | Disposition |
|---|---------|-------|------|-------------|
| 1 | prometheus | prom/prometheus:v2.54.1 | Scrape + TSDB store | REPLACE (monitoring MCP) |
| 2 | node-exporter | prom/node-exporter:v1.8.2 | Host metrics feed | REPLACE (psutil) |
| 3 | alertmanager | prom/alertmanager:v0.27.0 | Alert routing/silencing | REPLACE (alerting MCP) |
| 4 | victoria-logs | victoriametrics/victoria-logs:v1.10.0 | Log storage | REPLACE (DB/stdlib) |
| 5 | grafana | grafana/grafana:11.1.0 | Dashboards | REPLACE (admin module UI) |
| 6 | cadvisor | gcr.io/cadvisor/cadvisor:v0.51.0 | Container metrics | REPLACE |
| 7 | blackbox-exporter | prom/blackbox-exporter:v0.25.0 | Uptime probes | REPLACE (in-app self-report) |

Volumes freed at removal: `prometheus_data`, `alertmanager_data`, `grafana_data`.

### What the backend ALREADY owns (the hard parts — stays)

| Piece | Location | Notes |
|---|---|---|
| In-app instruments | `app/features/monitoring/infrastructure/metrics.py` | `prometheus_client` **pip library** (not the container): Counter/Gauge/Histogram, CollectorRegistry |
| `/metrics` endpoint | `app/main.py` (~L134) | Containers only scrape this — cutting containers does not cut this |
| Threshold rule engine | `app/features/monitoring/domain/thresholds.py` | Emits Findings (p95 latency, HTTP 5xx rate, DB p95) at healthy/warning/critical lines |
| `ScanResult` | `telemetry.scan_result` | Full scan verdict per subsection (status enum, findings, root_causes, actions, confidence, model, prompt_hash, windows) |
| `StatusTransition` | `telemetry.status_transition` | Incident log; durations derived, not stored |
| `ToolCallAudit` | `telemetry.tool_call_audit` | Reconciler key `metric_key` present — the anti-hallucination contract |
| `HealthMetric` | `telemetry.health_metric` | Web+Android snapshots: uptime, p50/p95/p99, HTTP 2xx/4xx/5xx %, CPU/RAM/disk/net, DB connections |
| Request logging middleware | `app/core/monitoring.py` | Skips health/metrics paths |
| Daily aggregation worker | `app/core/analytics.py` | Pre-computed metrics |
| Crash MCP (separate process) | `mcp-crash-monitor/` | Already exists at repo root |
| Scan agent contract | `docs/observability/SCAN-AGENT.md` | System prompt, schema, tool rules, reconciliation — the SPEC |

### Free LLM providers already wired in `.env.example`

`LLM_BASE_URL`/`LLM_API_KEY` (generic OpenAI-compatible), `NVIDIA_NIM_API_KEY`,
`OPENROUTER_API_KEY` (free models), `OLLAMA_BASE_URL` (local). **Zero paid providers
may enter any production path.**

### The gap analysis (what actually has to be built)

1. `HealthMetric` rows are fed by node_exporter/cadvisor scrape → need an in-app writer.
2. `thresholds.py` source label is `prometheus` → repoint to the in-app store.
3. Blackbox uptime probes → self-report via middleware + scheduled task.
4. MCPs monitoring/alerting/security/analyst do not exist yet (only crash-monitor).
5. Grafana-equivalent admin UI does not exist yet.

---

## 1. Target bundled directory tree

```
backend/app/
├── mcp/                          # BUNDLE: all house-built MCPs, each self-contained
│   ├── core/                     # shared tool layer (read-only rule, 5s timeouts,
│   │                             #  row caps, table allowlists, audit logging)
│   ├── monitoring/               # MCP #1 — Prometheus replacement
│   ├── alerting/                 # MCP #2 — Alertmanager replacement
│   ├── security/                 # MCP #3 — bug/threat/malware scans
│   └── analyst/                  # MCP #4 — AI admin brain feeding the dashboard
├── llms/                         # BUNDLE: named per-feature LLM wrappers
│   ├── __init__.py               # provider router — free-only allowlist
│   ├── analyst.py                # -> admin security/bug intelligence
│   ├── timetable_parser.py       # -> exam/timetable feature
│   └── feedback_voice.py         # -> feedback sentiment
├── observability/
│   ├── metrics.py                # in-app collector (no exporters)
│   ├── thresholds.py             # SCAN-AGENT §5 tables, in code
│   └── store.py                  # writer into existing DB (no new storage service)
└── features/                     # (existing, per AGENTS.md rules — business logic)

frontend/src/modules/admin/features/
├── monitoring/                   # BUNDLE: Grafana replacement — compact cards,
│                                 #  progress bars, zero-scroll tabs
└── ...existing...
```

Every bundle is independently maintainable: swap/debug one MCP or LLM mapping without
touching the others.

---

## 2. Phases (each closes only after verification passes and all bugs are fixed)

### Phase 0 — Baseline freeze (DONE)
Read-only inventory above; parity checklist defined below. Zero modifications.

### Phase 1 — MCP core bundle
- Create `backend/app/mcp/core/`: tool registry, `tool_call_audit` enforcement,
  read-only verification, DB table allowlists, 5s timeouts, 10k row caps.
- Create `backend/app/llms/__init__.py`: provider router restricted to free providers
  (NVIDIA NIM / OpenRouter free models / Ollama), keyed off existing env vars.
- NO new pip dependencies. `prometheus_client` and `psutil` are tiny, open-source.
- **Verify:** unit tests — audit row written and read back for a fake tool call;
  router refuses a paid-provider config; full pytest suite green.

### Phase 2 — Monitoring MCP (Prometheus + node/cadvisor replacement)
- `observability/collector.py`: records requests, latency, 5xx, auth failures from the
  existing middleware into `telemetry.health_metric` (existing table).
- `observability/store.py`: host CPU/RAM/disk via `psutil`; uptime self-report.
- `mcp/monitoring/`: query API exposing the A-W/B-A subsection metrics.
- Repoint `thresholds.py` from `"prometheus"` source to the in-app store.
- **Verify:** real requests produce rows; numbers match manual counts; the §5
  thresholds table reproduces identical healthy/warning/critical verdicts from the
  new source; `test_monitoring.py` extended and green.

### Phase 3 — Alerting MCP (Alertmanager replacement)
- `mcp/alerting/`: threshold breach → dedupe (fire once per window) → email via
  existing SMTP config → tracked in its own audit table.
- **Verify:** simulated breach sends exactly one email; second breach in window is
  silenced; happy path + 401 tests green.

### Phase 4 — Security MCP + AI Analyst (intellectual core — owner directive 5)
- `mcp/security/`: failed-login clustering, injection-attempt detection in feedback
  rows, token misuse signals.
- `mcp/analyst/`: LLM analyst produces structured findings with machine-verifiable
  evidence (`tool_call_audit` reconciliation, per SCAN-AGENT §3); planted prompt
  injections in data are reported as findings, never obeyed.
- Admin UI (`admin/features/monitoring/`): security-health progress bar, threat
  cards, compact grid. Page does not scroll horizontally; vertical scroll only
  within a card. Lazy-loaded; bundle size checked before merge.
- **Verify:** `npx tsc`, `npm run build`, lint, bundle-size budget; reconciliation
  correctly rejects a fabricated number; scan of a clean DB returns healthy, not error.

### Phase 5 — Directory bundling (owner directive 2)
- Execute the tree above; slim `ops/` to `ops/_legacy/` (kept read-only as reference).
- LLM-feature mapping enforced by a test (each `llms/*.py` maps to exactly one feature).
- **Verify:** shared-layer purity (`grep -r "from.*features" src/shared` = zero),
  build chunk sizes recorded and compared, all tests green.

### Phase 6 — Removal (owner directive 1 — parity gate)
- All 7 monitoring containers deleted + 3 volumes + `ops/_legacy/` in ONE commit,
  only after the parity checklist below passes for a full parity week.
- **Verify:** `docker compose config` valid; app boots with no removed service;
  documented rollback path (revert commit = restore).

### Phase 7 — Feature expansion (owner directive 4) — continuous
- New features each carry: name, bundle location, LLM file used (if any),
  free-tier cost check, happy+401 test, progress-bar surface for its subsystem.
- Running app size budget re-checked every phase; **bulky = that phase rolls back.**

---

## 3. Parity checklist (the Phase 6 deletion gate)

Status values: `pending` → `implemented (MCP settled, 7-day gate running)` →
`verified`. A row only becomes `verified` when its MCP reproduces the old
behavior AND the `test_monitoring.py` suite passes against the new source for
7 consecutive days.

| # | Requirement | Current owner | MCP owner | Status |
|---|-------------|---------------|-----------|--------|
| 1 | p95 latency finding | thresholds.py | health_metric (in-app histogram deltas) | implemented (Phase 2) — gate running |
| 2 | HTTP 5xx-rate finding | thresholds.py | health_metric (in-app HTTP mix) | implemented (Phase 2) — gate running |
| 3 | DB query p95 finding | thresholds.py | health_metric (in-app histogram deltas) | implemented (Phase 2) — gate running |
| 4 | 8 subsection ScanResult verdicts | telemetry.scan_result | analyst MCP | pending |
| 5 | Incident transitions | telemetry.status_transition | monitoring MCP | pending |
| 6 | Tool-call audit + reconciliation | telemetry.tool_call_audit | mcp/core (Phase 1) | implemented (Phase 1) — gate running |
| 7 | Host CPU/RAM/disk/net | node_exporter + cadvisor | psutil via observability/host | implemented (Phase 2) — gate running |
| 8 | Uptime probes | blackbox-exporter | reader-derived coverage (observability/uptime) | implemented (Phase 2) — gate running |
| 9 | Alert routing + silencing | alertmanager | alerting MCP + SMTP | pending |
| 10 | Dashboards | grafana | admin UI | pending |

A row may only be checked when its MCP reproduces the old behavior AND the
`test_monitoring.py` suite passes against the new source for 7 consecutive days.

Implementation notes for the implemented rows (Phase 2, verified by tests):

- Rows 1–3 were already fed by the in-app instruments (`health.sample_once`
  writes `telemetry.health_metric` from `prometheus_client` deltas) — Phase 2
  repointed the `thresholds.py` Finding source labels from `prometheus` / the
  external exporters (`node_exporter`, `uptime_kuma`) to the actual stores:
  `health_metric` and `psutil`.
- Row 7 is `observability/host.py`: psutil read in-process, per-metric failure
  isolation, network bytes as deltas with a reboot-safe floor of 0.
- Row 8 is `observability/uptime.py`: uptime is computed at read time from
  sample coverage (anchored to the platform's oldest surviving sample);
  rows keep `uptime_pct` NULL by design, the A_W collector no longer needs an
  external prober to fill it.

---

## 4. Free-only gate (applies to EVERY phase)

- No paid API, no trial-expiring service, no free-tier-that-bills-later dependency.
- Providers allowed: NVIDIA NIM (free tier), OpenRouter (free models only),
  Ollama (local), SMTP (existing Gmail app password). Anything else needs owner sign-off.
- Every new dependency must be: open-source, merged into the bundle, and justified for
  bundle size.
