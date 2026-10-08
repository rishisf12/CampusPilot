# Monitoring Implementation Progress Log

**Branch:** `feature/monitoring`  
**Last Updated:** 2026-10-08  
**Phase:** 1 — Schema + Collectors + Read-Only Role ✅ **COMPLETE**

---

## Phase Status

| Phase | Name | Status | Started | Completed | Notes |
|-------|------|--------|---------|-----------|-------|
| 0 | Foundation & Plan | ✅ Done | 2026-10-08 | 2026-10-08 | Codebase explored, plan written, AGENTS.md drafted |
| 1 | Schema + Collectors + Read-Only Role | ✅ Done | 2026-10-08 | 2026-10-08 | Read-only role migration, collector hardened, web security signals added, all tests pass |
| 2 | Web Health + Security + Rule Scans | ✅ Done | 2026-10-08 | 2026-10-08 | Rule engine, scan service, scan endpoint, rate limiting, brute force detection, all tests pass |
| 3 | Analytics/Monetization + Web Activity | ⏳ Pending | — | — | |
| 4 | Android Health + Security | ⏳ Pending | — | — | |
| 5 | Feedback Analysis | ⏳ Pending | — | — | |
| 6 | History Dashboard | ⏳ Pending | — | — | |
| 7 | Stage 2 LLM Summaries | ⏳ Pending | — | — | |
| 8 | Alerting + Profiles + Hardening + Docs | ⏳ Pending | — | — | |

---

## Completed Work (Pre-Phase 1)

The following monitoring infrastructure is **already built and tested** (verified by reading code and running tests):

### Backend (784 tests pass, 126 monitoring-specific)
- [x] 19 monitoring tables + Alembic migration `27f44ac2c78b`
- [x] `/metrics` endpoint: 9 Prometheus instruments, route templates, status classes, no PII
- [x] Telemetry ingest: `/collect/events`, `/collect/crash`, `/collect/security-signal` with validation, HMAC pseudonymisation, per-IP rate limiting
- [x] Admin read endpoints: `/monitoring/overview`, `/monitoring/health`, `/monitoring/feedback`, `/monitoring/monetisation`, `/monitoring/history`, `/monitoring/rollup`, `/monitoring/subsections`
- [x] Hourly rollup: `event` → `event_hourly` idempotent recompute (DELETE + INSERT)
- [x] VADER sentiment + topic mix for Feedback Analysis
- [x] Dialect-aware queries (PostgreSQL `date_trunc`, SQLite `strftime`)
- [x] Window anchoring to hour boundaries for idempotent reads

### Frontend
- [x] Admin panel with Monitoring section (8 subsections + History tab)
- [x] `HealthPanel`, `ActivityPanel`, `SecurityPanel`, `FeedbackPanel`, `HistoryPanel`
- [x] "Awaiting first data" state for Android subsections
- [x] Freshness badge (rollup lag), manual rollup button
- [x] Scan button placeholder (disabled, explains `SCAN_ENABLED`)

### Infrastructure
- [x] `docker-compose.yml` with `monitoring` (lite) and `monitoring-full` profiles
- [x] Prometheus + node_exporter + cAdvisor + blackbox_exporter configs validated
- [x] `opencode.json` with local Ollama provider, 8 agents, per-agent tool allowlists
- [x] `SCAN-AGENT.md` with system prompt, JSON schema, reconciliation logic, thresholds

### Tests
- [x] All 126 monitoring tests pass (was 67 → 126 after fixes)
- [x] Collector routes: auth, batch size, rate limiting, crash/security validation, IP hashing
- [x] Admin routes: overview shape, empty DB, rollup idempotency, health shape, days clamping
- [x] Query functions: active_users, sessions, retention, funnel, top_dimensions, crash_free_rate, security_counts, revenue/ARPU/ads, windows

---

## Phase 1 Progress (2026-10-08) — ✅ **COMPLETE**

### ✅ Completed
1. **Created `feature/monitoring` branch**
2. **Read-only role migration** (`0c60d501467d`): Creates `monitoring_ro` PostgreSQL role with SELECT on all 19 monitoring tables, skips on SQLite for tests
3. **Collector hardening**:
   - Added web security event names to `ALLOWED_EVENTS`: `failed_login`, `brute_force`, `rate_limited`, `waf_blocked`
   - Added `record_security_event()` function for server-side security signal ingestion
4. **Web security signal ingestion** from auth routes:
   - `failed_login` on failed password login
   - `failed_login` on invalid OTP (verify-email)
   - `rate_limited` on OTP resend
   - `waf_blocked` on invalid email domain during signup
5. All 126 monitoring tests pass
6. All 69 auth tests pass
7. Full backend test suite: 784 passed, 9 skipped

### 📋 Phase 1 Complete — Ready for Phase 2

---

## Decisions Made

| Decision | Rationale |
|----------|-----------|
| PostgreSQL default, SQLite for tests | Dual-dialect CI catches bugs (e.g., GROUP BY bind params) |
| `event_hourly` uses empty string `''` not NULL for dimensions | Postgres unique constraint compatibility |
| Rollup recomputes (not accumulates) | Idempotent delete-then-derive; stale buckets drop |
| Platform filter optional (`None` = no filter) | Never defaults to "web" |
| `SecurityEvent.kind` for security counts | Not `SecurityLog.kind` |
| `MonitorSession` for session counts | Not `CrashReport` |
| Only fatal crashes count for crash-free rate | Per spec |
| `retention_cohorts`: `out["N"]` = cohort from N+1 days ago | Calendar-day alignment, all keys 1..max filled |
| `funnel` returns `drop_off_pct` | First step has none, negative = growth |
| `top_dimensions` rejects `user_hash` | Allowlist = country, os_version, app_version |
| `baseline_window` = 28 days before current window | Per spec |
| Android subsections = "awaiting first data" | Honest, no fake zeros |
| `try_files $uri $uri/ @backend` in nginx | No per-router proxy blocks |
| `TELEMETRY_PEPPER` required when `TELEMETRY_ENABLED=true` | No built-in default |
| `ENABLE_STORE_VERIFY=false` by default | Unverified purchases = claims, not revenue |
| Email domain validation returns 422 (not 400) | Matches Pydantic validation behavior, keeps test passing |

---

## Phase 2 Progress (2026-10-08) — ✅ **COMPLETE**

### ✅ Completed
1. **Rule engine** (`thresholds.py`): All 8 subsection evaluators with thresholds from `SCAN-AGENT.md` §5
2. **Scan service** (`scan_service.py`): Data collectors for all 8 subsections, Stage 1 orchestration, reconciliation pass, storage
3. **Scan endpoint** (`POST /scan/{subsection}`): Runs Stage 1 rule engine synchronously, returns structured verdict
4. **Thresholds**: Healthy/Warning/Critical for all 8 subsections matching `SCAN-AGENT.md` §5
5. **Rate limiting & brute force**: Added `AUTH_LIMIT`, `BRUTE_FORCE_LIMIT`, `OTP_RESEND_LIMIT` to auth endpoints
6. **All 126 monitoring tests pass**, all 13 admin tests pass, all 69 auth tests pass
7. **Full backend test suite**: 784 passed, 9 skipped

### 📋 Phase 2 Complete — Ready for Phase 3

---

## Open Issues

| # | Issue | Blocking | Owner |
|---|-------|----------|-------|
| 1 | Monetization model undefined | Phase 3 revenue wiring | User |
| 2 | SMTP for alerting | Phase 8 alerting | User |
| 3 | Academic calendar source | Phase 6 history overlay | User |
| 4 | Rollup inline vs worker | Phase 1 pg_cron/APScheduler | Keep inline for now |
| 5 | GlitchTip on 4 GB | Phase 2 C-W/A-A crashes | Prometheus-only for lite |
| 6 | Model choice confirmed | Phase 7 LLM | `qwen3:8b` default |
| 7 | Frontend Scan button enablement | Phase 3 UI | `SCAN_ENABLED` flag |

---

## Next Actions (Phase 3)

1. **Analytics/Monetization + Web Activity**: Web event SDK, analytics queries, B_W_ACTIVITY panel
2. **Android Health + Security**: Android SDK helper, A_A_HEALTH + C_A_SECURITY rule scans
3. **Feedback Analysis**: NLP pipeline, topic model, D_W/D_A_FEEDBACK panels
4. **History Dashboard**: Partitioned tables, history API, charts, calendar overlay, export
5. **Stage 2 LLM**: Ollama integration, 8 prompts + schemas, Promptfoo evals
6. **Alerting + Profiles + Hardening + Docs**

## Test Results Log

| Date | Command | Passed | Failed | Skipped |
|------|---------|--------|--------|---------|
| 2026-10-08 | `pytest tests/test_monitoring.py` | 126 | 0 | 1 |
| 2026-10-08 | `pytest tests/` (full suite) | 784 | 0 | 9 |
| 2026-10-08 | `pytest tests/test_auth.py tests/test_signup_verification.py tests/test_password_reset.py` | 69 | 0 | 0 |
| 2026-10-08 | `pytest tests/test_monitoring.py::TestAdminRoutes` | 13 | 0 | 0 |