# CampusPilot Monitoring — Phased Implementation Plan

**Project:** CampusPilot ("Essential - Your Campus Assistant")  
**Branch:** `feature/monitoring` (to be created)  
**Status:** Phase 0 complete (exploration), ready for Phase 1

---

## 1. Codebase Exploration Summary

### Existing Stack (verified by reading code)
| Layer | Technology | Location |
|-------|------------|----------|
| Frontend | React 18 + Vite 5 + Tailwind | `frontend/` |
| Backend | FastAPI 0.115 + SQLModel + uvicorn on :8001 | `backend/backend/` |
| Database | PostgreSQL 16 (prod), SQLite (tests) | `backend/alembic/`, `database/classpilot.db` |
| Auth | JWT HS256 + WebAuthn/passkeys, email-domain allowlist | `features/auth/` |
| Monitoring infra | Prometheus + node_exporter + cAdvisor + blackbox_exporter | `docker-compose.yml`, `ops/prometheus/` |
| Admin panel | Single section "Feedback Responses" | `frontend/src/features/admin/` |

### Monitoring Already Built (Phase 1 infrastructure)
| Component | State | Evidence |
|-----------|-------|----------|
| 19 monitoring tables + Alembic migration `27f44ac2c78b` | ✅ Built | `features/monitoring/models.py`, migration file |
| `/metrics` (9 Prometheus instruments, route templates, no PII) | ✅ Built | `main.py:_metrics_middleware()`, `metrics.py` |
| Telemetry ingest (`/collect/events`, `/collect/crash`, `/collect/security-signal`) | ✅ Built | `collector.py`, `routes.py` |
| Admin read endpoints (`/monitoring/overview`, `/monitoring/health`, `/monitoring/feedback`, `/monitoring/monetisation`, `/monitoring/history`, `/monitoring/rollup`, `/monitoring/subsections`) | ✅ Built | `routes.py` |
| Hourly rollup (`event` → `event_hourly`) idempotent recompute | ✅ Built | `rollup.py` |
| VADER sentiment + topic mix for Feedback | ✅ Built | `feedback_analysis.py` |
| Web + Android monitoring UI (8 subsections, "awaiting first data" for Android) | ✅ Built | `Monitoring.jsx`, `Health.jsx`, `Activity.jsx`, `Security.jsx`, `Feedback.jsx`, `History.jsx` |
| All 784 backend tests passing (126 monitoring-specific) | ✅ Verified | `tests/test_monitoring.py` |

### Not Yet Built (remaining work)
| Deliverable | Phase |
|-------------|-------|
| Zero-cost audit table (SPDX, justification) | Phase 0 deliverable |
| Architecture diagram (Mermaid) | Phase 0 deliverable |
| Admin wireframes | Phase 0 deliverable |
| SQL schema doc | Phase 1 |
| REST API examples | Phase 1 |
| AI scan service (RQ worker, tools, 8 prompts, JSON schemas) | Phase 2-3 |
| Frontend charts pages (ECharts/Recharts) | Phase 2-3 |
| Android SDK snippet | Phase 3 |
| 8 subsection scan prompts | Phase 2-3 |
| `opencode.json` + tool allowlists | Phase 2 |
| Alerting (Telegram/Apprise/SMTP) | Phase 8 |
| Security/privacy checklist | Phase 8 |
| Testing plan + Promptfoo evals | Phase 8 |

---

## 2. Assumptions & Questions

### Assumptions
1. **PostgreSQL is the production database** — SQLite only for fast unit tests
2. **No Android app exists** — React Native project not in this repo; Android subsections ship with "awaiting first data"
3. **Single VPS deployment** — `docker-compose.yml` with `monitoring` (lite) and `monitoring-full` profiles
4. **Local LLM only** — Ollama on same host, no API keys, no egress
5. **Monitoring schema is separate** — reads from main DB but never writes to core tables
6. **Feedback Responses feeds Feedback Analysis** — existing table reused, no changes to it

### Questions for User
1. **Monetization model:** The code has `Purchase`, `AdEvent`, `Subscription` tables but no active monetization. Should I wire ad events / IAP collectors or leave as scaffold?
2. **SMTP limits:** Gmail SMTP has daily quotas. Do you have an alternative (self-hosted Postfix, Mailgun free tier, etc.) for alerting emails?
3. **Academic calendar data:** For the historical dashboard's "exam week overlay" — is there a CSV/ICS source, or should I seed a static JSON?
4. **Rollup worker:** Currently inline (`ROLLUP_INLINE=true`). Keep as-is for single replica, or extract to separate service now?
5. **GlitchTip vs Prometheus-only for crashes:** GlitchTip needs Redis (~50 MB). On 4 GB lite, Prometheus counters may suffice. Preference?

---

## 3. Phased Plan

### Phase 0: Foundation (this document)
- [x] Explore codebase, document findings
- [x] Write `docs/MONITORING_PLAN.md` (this file)
- [x] Create `docs/MONITORING_PROGRESS.md` (living log)
- [x] Draft `AGENTS.md` rules (see below)
- [x] Create `feature/monitoring` branch
- [ ] **WAIT FOR APPROVAL** before Phase 1

### Phase 1: Monitoring Schema + Collectors + Read-Only Role
**Goal:** Data exists, rule-based scans work, no AI yet

| Task | Details |
|------|---------|
| 1.1 | Verify monitoring schema is in separate namespace (already: `public` but logically isolated) |
| 1.2 | Read-only PostgreSQL role `monitoring_ro` with `SELECT` on monitoring tables only |
| 1.3 | FastAPI middleware already instruments `/metrics` — verify all 9 metrics export |
| 1.4 | `/collect/events` validation: body cap 200, event allowlist, HMAC user_hash, truncated IP hash |
| 1.5 | `/collect/crash` + `/collect/security-signal` validation (kind allowlist, required fields) |
| 1.6 | Per-IP rate limiting (sliding window, 30 req/min for events, 10/min for crashes) |
| 1.7 | Hourly rollup: `event` → `event_hourly` with `DELETE` + `INSERT` idempotent pattern |
| 1.8 | Prune job: raw `event` older than 13 months, `crash_report` older than 13 months |
| 1.9 | `pg_cron` or APScheduler for rollup + prune (if `ROLLUP_INLINE=false`) |
| 1.10 | Unit tests: collector validation, rollup idempotency, dialect parity (SQLite + PG) |
| 1.11 | **New:** Web security signals (failed_login, brute_force, rate_limited, waf_blocked) from middleware |

**Deliverables:** Migrations, collector endpoints, rollup CLI, read-only role, tests

---

### Phase 2: Web Health + Security Subsections + Rule-Based Scans
**Goal:** A_W_HEALTH and C_W_SECURITY show real data; "Scan now" returns Stage 1 (rules) verdict

| Task | Details |
|------|---------|
| 2.1 | `HealthPanel` already reads `health` endpoint — verify all fields populated |
| 2.2 | `SecurityPanel` reads `overview.security.counts` + `blocked` — verify `SecurityEvent` ingestion |
| 2.3 | Rule engine: thresholds from `SCAN-AGENT.md` §5 (p95, 5xx, uptime, failed logins, CVEs) |
| 2.4 | Stage 1 scan output: JSON schema from `SCAN-AGENT.md` §2, status = Healthy/Warning/Critical |
| 2.5 | Reconciliation pass: re-query every cited metric, fail scan if mismatch >2% |
| 2.6 | Scan queue: RQ worker (BSD-3), `concurrency=1`, timeout 240s, max 12/hour |
| 2.7 | `POST /scans/{subsection}` endpoint stores `ScanResult` + `StatusTransition` + `ToolCallAudit` |
| 2.8 | `GET /scans/history` returns paginated scans + incidents + tool calls |
| 2.9 | Frontend: enable `ScanButton` when `SCAN_ENABLED=true`, show Stage 1 card |
| 2.10 | Promptfoo evals: rule-engine correctness, threshold boundaries, no-hallucination |

**Deliverables:** Rule engine, scan queue, 2 working scans (A-W, C-W), frontend integration, Promptfoo suite

---

### Phase 3: Analytics/Monetization Collectors + Web Activity
**Goal:** B_W_ACTIVITY shows DAU, retention, funnels, revenue (verified/unverified split)

| Task | Details |
|------|---------|
| 3.1 | Web collector SDK: tiny `fetch` wrapper (`event_name`, `props`, auto-session, HMAC user_hash) |
| 3.2 | `/collect/events` already accepts batches — verify schema: `app_open`, `screen_view`, `page_view`, `session_start`, `session_end`, `feature_use`, `purchase`, `ad_impression`, `ad_click` |
| 3.3 | `sessions` table rollup on `session_end` (duration, event_count) |
| 3.4 | DAU/WAU/MAU via `monitoring_session.started_at` distinct `user_hash` |
| 3.5 | New vs returning: first `session_start` in window vs before window |
| 3.6 | Retention cohorts: calendar-day aligned, 90-day lookback, fill all keys 1..max with zeros |
| 3.7 | Funnel: drop-off % (not conversion), negative = growth, first step has no drop-off |
| 3.8 | Top dimensions: allowlist = country, os_version, app_version (reject `user_hash`) |
| 3.9 | Revenue: verified vs unverified split, ARPU = verified_revenue / active_users |
| 3.10 | Ad performance: impressions, clicks, eCPM = revenue_micros / (impressions/1000) |
| 3.11 | `ActivityPanel` already expects `active_users`, `sessions`, `events`, `new_vs_returning`, `retention`, `countries`, `versions`, `hourly` — wire all |

**Deliverables:** Web event SDK, analytics queries, monetization queries, B_W_ACTIVITY panel working

---

### Phase 4: Android Health + Security Subsections
**Goal:** A_A_HEALTH and C_A_SECURITY scaffolds ready; Android SDK helper written

| Task | Details |
|------|---------|
| 4.1 | Android SDK (Kotlin): `MonitoringCollector` class with `sendEvents()`, `sendCrash()`, `sendSecuritySignal()` |
| 4.2 | Crash/ANR: `kind`="crash"/"anr", `fingerprint` (exception+top frames hash), `fatal`, `foreground` |
| 4.3 | Security signals: `root_detected`, `emulator_detected`, `tamper_detected`, `hook_detected`, `debugger_detected` |
| 4.4 | Source maps: upload mapping file to GlitchTip (optional, full profile) |
| 4.5 | Crash-free rate: sessions from `monitoring_session`, only fatal crashes count |
| 4.6 | ANR rate, startup time (cold), slow frames % (jank), API failure rate |
| 4.7 | Breakdowns: app_version, Android version, device_model, network_type (wifi/cellular) |
| 4.8 | `HealthPanel` + `SecurityPanel` already handle `awaiting` state for Android — verify |
| 4.9 | Rule thresholds for Android (from `SCAN-AGENT.md` §5) |

**Deliverables:** Android SDK snippet (copy-paste), A_A_HEALTH + C_A_SECURITY rule scans

---

### Phase 5: Feedback Analysis (connects to existing Feedback Responses)
**Goal:** D_W_FEEDBACK + D_A_FEEDBACK show sentiment, topics, complaints, crash correlation

| Task | Details |
|------|---------|
| 5.1 | VADER sentiment (NLTK, Apache-2.0) — already in `feedback_analysis.py` |
| 5.2 | Topic clustering: BERTopic (MIT) for full profile; keyword/TF-IDF+NMF for lite |
| 5.3 | Rating trends (if feedback has rating field) |
| 5.4 | Top complaints / feature requests extraction |
| 5.5 | Correlation: feedback spike vs crash cluster vs release deploy |
| 5.5 | `FeedbackPanel` already expects `total`, `sampled`, `truncated`, `sentiment`, `topics` — wire all |
| 5.6 | Hourly/daily `FeedbackAnalysis` snapshots via rollup-style job |

**Deliverables:** NLP pipeline, topic model, correlation logic, D_W/D_A_FEEDBACK panels working

---

### Phase 6: History Dashboard
**Goal:** Global timeline + per-subsection history with heatmap, export, academic calendar

| Task | Details |
|------|---------|
| 6.1 | `HistoryPanel` already reads `/monitoring/history` — verify scans, incidents, tool_calls |
| 6.2 | Hourly rollups in `event_hourly`, daily in `event_daily` (partitioned) |
| 6.3 | PostgreSQL native partitioning: `event_hourly` by `bucket_hour` (monthly partitions) |
| 6.4 | Drop old partitions instead of DELETE (retention: raw 30d, hourly 90d, daily 2y) |
| 6.5 | Incident log from `StatusTransition` (open = no closing Healthy) |
| 6.6 | Date-range picker (24h/7d/30d/90d/custom), period-vs-previous comparison |
| 6.7 | Trend charts: Apache ECharts (MIT) or Recharts (MIT) |
| 6.8 | Release markers from local `git log --since=` (no GitHub API) |
| 6.9 | Academic calendar overlay: static JSON seeded from IIITDM calendar (mid-sem, end-sem, holidays, timetable upload) |
| 6.10 | CSV/JSON export endpoint |

**Deliverables:** Partitioned tables, history API, frontend charts, calendar overlay, export

---

### Phase 7: Stage 2 Local LLM Summaries
**Goal:** 8 scan prompts with JSON schemas, LLM summaries on Standard profile, Promptfoo evals

| Task | Details |
|------|---------|
| 7.1 | Ollama service in docker-compose (MIT), models: `qwen3:8b` (lite), `qwen3:30b-a3b` (full), `phi-3.5-mini` (fallback) |
| 7.2 | `opencode.json` with local Ollama provider, 8 agents (one per subsection), per-agent tool allowlists |
| 7.3 | 8 system prompts (one per subsection) — load from `SCAN-AGENT.md` |
| 7.4 | JSON schema validation (Pydantic) + reconciliation pass (already designed) |
| 7.5 | Stage 2 flow: if Ollama available → LLM summary; else → Stage 1 template text |
| 7.6 | Model loading: `keep_alive=0` (unload after each scan) to fit 4 GB |
| 7.7 | Promptfoo regression suite: accuracy, hallucination rate, prompt-injection resistance |
| 7.8 | Garak (Apache-2.0) for red-team testing (full profile only) |

**Deliverables:** `opencode.json`, 8 prompts + schemas, Ollama integration, Promptfoo suite

---

### Phase 8: Alerting + Docker Profiles + Hardening + Docs
**Goal:** Production-ready, alerting works, both profiles validated, docs complete

| Task | Details |
|------|---------|
| 8.1 | Alerting: Telegram bot (MIT) or Apprise (MIT) via existing SMTP — rules from `ops/prometheus/alerts.yml` |
| 8.2 | Auto-scan on Critical alert (optional, opt-in) |
| 8.3 | `docker-compose.yml` profiles: `monitoring` (lite, ~3.9 GB), `monitoring-full` (full, ~9 GB) |
| 8.4 | PostgreSQL tuning per profile: `shared_buffers`, `work_mem`, `max_connections` |
| 8.5 | Security hardening: read-only role, `SCAN_CONCURRENCY=1`, tool allowlists, network isolation |
| 8.6 | Privacy: DPDP-style consent, HMAC user_hash, no raw emails/roll numbers in monitoring tables |
| 8.7 | Backup: `pg_dump` + cron, rotation, tested restore |
| 8.8 | Final docs: architecture diagram, wireframes, schema doc, API examples, security checklist, roadmap, testing plan |

**Deliverables:** Alerting rules, docker profiles, hardening, all docs

---

## 4. Hardware Profiles & PostgreSQL Tuning

| Profile | RAM | CPU | Disk | PostgreSQL Tuning |
|---------|-----|-----|------|-------------------|
| **MINIMAL (2 GB)** | 2 GB | 1 vCPU | 20 GB | `shared_buffers=128MB`, `work_mem=4MB`, `max_connections=50`, no LLM, no Grafana, Prometheus 7d retention, Uptime Kuma, rule scans only |
| **STANDARD (4 GB)** | 4 GB | 2 vCPU | 40 GB | `shared_buffers=256MB`, `work_mem=8MB`, `max_connections=100`, `qwen3:8b` Q4 loaded on-demand (`keep_alive=0`), Prometheus 15d, VictoriaLogs 7d, GlitchTip optional |
| **OPTIONAL (8 GB+)** | 8-16 GB | 4-6 vCPU | 80-160 GB | `shared_buffers=1-2GB`, `work_mem=16-32MB`, `max_connections=200`, `qwen3:30b-a3b`, Loki, Umami, Superset, ZAP full, MobSF, BERTopic |

---

## 5. Zero-Cost Audit (preliminary)

| Tool | Category | SPDX | Profile | Why Truly Free | RAM | Risk |
|------|----------|------|---------|----------------|-----|------|
| Ollama | LLM runtime | MIT | Standard | MIT server + Apache-2.0 model weights | 1.6-2 GB | Model pulls |
| qwen3:8b / 30b-a3b | Model | Apache-2.0 | Std/Full | OSI-approved weights, no use restrictions | 5/18 GB disk | Large disk |
| opencode | Agent runner | MIT | All | MIT, localhost HTTP only | ~50 MB | None |
| Prometheus | Metrics | Apache-2.0 | All | Apache-2.0, no enterprise split | 250 MB | Retention math |
| node_exporter | Host metrics | Apache-2.0 | All | Apache-2.0 | 20 MB | None |
| cAdvisor | Container metrics | Apache-2.0 | Full | Apache-2.0, read-only docker socket | 100 MB | Needs privileged |
| Uptime Kuma | Uptime/SSL | MIT | Full | MIT, self-hosted | 180 MB | Node service |
| VictoriaLogs | Logs (lite) | Apache-2.0 | Std | Apache-2.0 single-node | 400 MB | UNVERIFIED: confirm no enterprise split |
| GlitchTip | Crashes | MIT | Full | MIT fork of Sentry, SDKs MIT | 500 MB | UNVERIFIED: confirm no enterprise gating |
| Trivy | CVE scanner | Apache-2.0 | All | Apache-2.0, public DB | 250 MB | Offline DB pull = one-time egress |
| OSV-Scanner | Dep CVE | Apache-2.0 | All | Apache-2.0, queries osv.dev | 100 MB | **Egress per call** — use offline mirror |
| Gitleaks | Secret scan | MIT | All | MIT | 50 MB | None |
| testssl.sh | TLS audit | GPL-2.0 | All | GPL-2.0 script | 20 MB | Slow |
| OWASP ZAP | DAST | Apache-2.0 | Full | Apache-2.0 | 300 MB | **Active scan mutates data** — staging only |
| CrowdSec | WAF/bouncer | MIT | Full | MIT console + agents | 200 MB | UNVERIFIED: enterprise tiers exist |
| Semgrep CE | SAST | LGPL-2.1 | Full | LGPL-2.1 community | 400 MB | UNVERIFIED: 2024 license change |
| spaCy + VADER | NLP | MIT/Apache-2.0 | All | spaCy MIT, VADER Apache-2.0 | 200 MB | Model weights have separate licenses |
| Promptfoo | LLM evals | MIT | All | MIT, local runner | 100 MB | None |
| Umami | Analytics | MIT | Full | MIT (v2), **blocked on SQLite** | 150 MB | UNVERIFIED: v3 relicensing |
| Grafana | Dashboards | AGPL-3.0 | All | AGPL-3.0, OSI-approved | 350 MB | AGPL network copyleft |
| PgBouncer | Connection pool | ISC | Optional | ISC | 20 MB | Only if needed |

**Removed for Cost/RAM:**
| Tool | Reason |
|------|--------|
| Loki | AGPL + heavier than VictoriaLogs; skip on 4 GB |
| Falco | Licensing flux; CrowdSec+Coraza covers same ground |
| Wazuh | Heavy, AGPL, overlapping with CrowdSec |
| Suricata | Heavy, GPL, overlapping |
| Android emulator automation | Needs KVM, unstable in containers |
| SearXNG | Egresses queries to upstream; default OFF |
| GitHub MCP | Calls api.github.com; default OFF |

---

## 6. AGENTS.md (Proposed Rules for This Project)

```markdown
# AGENTS.md — CampusPilot Project Conventions

## Commands
- Backend tests: `cd backend/backend && python -m pytest -v`
- Frontend dev: `cd frontend && npm run dev`
- Type check: `cd frontend && npm run typecheck`
- Lint: `cd backend/backend && ruff check .` (pre-existing errors OK, no new)
- Monitoring smoke: `cd backend/backend && python tools/smoke_monitoring.py`
- Docker up: `docker compose up --build -d`
- Docker monitoring: `docker compose --profile monitoring up -d`

## Safety
- Never commit `.env`, secrets, API keys, DB dumps, uploads
- Roll numbers and @iiitdmj.ac.in emails are PII — hash in logs/fixtures
- `pg_dump` before any migration; migrations must be reversible
- Monitoring writes to monitoring schema only; fail silently if down
- No student data in chat or tool output

## Code Style
- Python: type hints, docstrings for public functions, SQLModel not raw SQL
- React: functional components, hooks, Tailwind classes
- SQL: explicit columns, no `SELECT *`, indexes on filter columns
- Commits: one logical step, conventional messages (`feat:`, `fix:`, `chore:`)

## Monitoring-Specific
- All 8 scans read-only; `concurrency=1` enforced in RQ worker
- Stage 1 (rules) always runs; Stage 2 (LLM) only on Standard+
- Reconciliation pass mandatory — hallucinated numbers fail the scan
- Tool allowlists per scan, enforced server-side
- Untrusted data (feedback, logs, crashes) wrapped in `<untrusted-data>` blocks
```

---

## 7. Open Issues / Decisions Needed

| # | Issue | Impact | Decision |
|---|-------|--------|----------|
| 1 | Monetization active? | Determines B_W/B_A revenue wiring | Ask user |
| 2 | SMTP for alerting? | Gmail quota vs self-hosted | Ask user |
| 3 | Academic calendar source? | History dashboard overlay | Ask user |
| 4 | Rollup inline vs worker? | Single replica vs future scaling | Keep inline for now |
| 5 | GlitchTip on 4 GB? | 500 MB RAM vs Prometheus-only | Prometheus-only for lite |
| 6 | Model choice confirmed? | `qwen3:8b` Apache-2.0 vs `phi-3.5-mini` MIT | `qwen3:8b` default |

---

## 8. Next Step

**Awaiting your approval to:**
1. Create `feature/monitoring` branch
2. Start Phase 1 (schema verification, read-only role, collector hardening, tests)
3. Save this plan to `docs/MONITORING_PLAN.md`

Once approved, I'll begin Phase 1 with small, verifiable commits and test output at each step.