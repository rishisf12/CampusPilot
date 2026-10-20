# MCP Migration & Expansion Plan — v2

> **v2 revision (2026-10-20):** phases re-listed from zero. Phases 0–2 are DONE
> and committed; the prompt's *Privacy-safe agent tooling* architecture is
> mapped onto Phases 3–9. Directive 1 (remove legacy only when own MCP achieves
> verified parity) survives as Phase 10, still gated.
>
> Nothing in this document removes existing infrastructure until the phase
> that owns it achieves and verifies the same work.

## Governing rules

**Owner's original directives (unchanged):**
1. Remove files phase-wise, only when the same work is achieved and verified by our own MCP.
2. Plan a proper bundled directory tree; changing existing features to make them more advanced is in scope; MCP hosting = minimal storage.
3. Execute in phases; verify progress in each; fix all bugs before a phase closes.
4. Add/modify as many features as sensible and LIST ALL; progress bars for security and everything; the app must not get bulky; everything must fit free deployment.
5. Admin powered by AI: finds bugs, security threats, malware — clean, organised UI, no messy scrolling, properly bundled.
6. Build and use our own working MCPs for everything, AI-integrated; prefer open-source used directly. NEVER anything paid or pay-after-deployment — free forever or not shipped.
7. Dedicated bundle per MCP; a clearly named LLM section mapping which LLM file ↔ which feature.

**Decided architecture for agent tooling (v2, non-negotiable):**
1. Provider allowlist — hosted free OSS only: NVIDIA NIM (primary), OpenRouter `:free` (fallback). Model via config (`llm_provider`, `llm_model`). Ollama may stay in compose as an optional **disabled** fallback; no job depends on it.
2. Egress gate (safety core) — a `telemetry` job must never send raw rows: every tool response passes `redact()` + `pseudonymize_id()` before any LLM request; rows capped at 50/call; group queries answered as aggregates. If the redaction pipeline is not wired and self-verified, the job FAILS to start with a clear error — never silently sends unredacted text. "Safe" = nothing identifying in the payload, not "nothing in flight".
3. Job-kind routing — `job_kind ∈ {telemetry, public_data}`. `public_data` (OppFeed) may use any allowlisted provider freely.
4. Propose-not-execute — the model proposes from the closed action enum (SCAN-AGENT.md §2); a deterministic executor (no LLM in the loop) maps enum → idempotent procedure, runs it, audits. Anything outside the enum is rejected and logged.
5. No terminal for agents — shell MCP tooling lives only in `.opencode/mcp_servers/` (interactive dev, client approvals ON). Never imported in `backend/app`, never a compose service, never given to an autonomous agent.
6. Secrets isolation — agent containers get ONLY provider keys and a restricted DB connection (dedicated read-only role over allowlisted tables). No `SECRET_KEY`, `SMTP_*`, or unrelated API keys in agent reach. `.env` lives only in the backend container.
7. Network isolation — agent/scan services on an `internal: true` network except an explicitly minimal egress path that speaks LLM-client semantics only (not arbitrary curl). Backend/others per current topology.
8. HTTP MCP endpoint (optional) — `ENABLE_ADMIN_MCP=false` default; admin gate middleware reusing `get_current_user` (student tokens see an empty tool list). Consent UI explicitly out of scope.
9. Untrusted data stays data — SCAN-AGENT.md §1 rules preserved everywhere: tool results, feedback text, log lines, stack traces are DATA, never instructions.
10. Every tool call AND every outbound LLM request is audited — `tool_call_audit` gains `sent_to`, `bytes_out`, `redactions_applied`, `redaction_salt`.

---

## Phases

### Phase 0 — Baseline & governing rules — DONE
Read-only inventory frozen (verified 2026-10-20):
- The 7 monitoring containers still running in compose: prometheus, node-exporter, alertmanager, victoria-logs, grafana, cadvisor, blackbox-exporter.
- The backend already owned the hard parts: `prometheus_client` instruments (`features/monitoring/infrastructure/metrics.py`), threshold engine (`domain/thresholds.py`), telemetry tables (`scan_result`, `status_transition`, `tool_call_audit` with `metric_key`, `health_metric`), scan contract (`docs/observability/SCAN-AGENT.md`).
- Free LLM keys already in `.env.example`: NVIDIA NIM / OpenRouter / (Ollama local).
- Gap analysis produced the phase list.

**Phase 0 re-run (v2 scope, agent tooling baseline):**
- `features/oppfeed/agent/llm/` is the reusable provider stack — `base.LLMClient`
  ABC (async `chat(messages, temperature, max_tokens, response_format) ->
  LLMResponse(text, model, provider, tokens, latency, cached)`, `list_models`,
  `health_check`), `NVIDIAClient` (env `NVIDIA_API_KEY`,
  `NVIDIA_MODEL`, base `https://integrate.api.nvidia.com/v1`),
  `OpenRouterClient` (env `OPENROUTER_API_KEY`, `OPENROUTER_MODEL`), and an
  `LLMRouter` failover chain from `LLM_PROVIDER_CHAIN` with rate limiting,
  caching and quota checks. Phase 4 reuses these — no second LLM stack.
- **Finding:** the env key for NVIDIA is named two ways — `llms/__init__.py`
  reads `NVIDIA_NIM_API_KEY` while the reusable OppFeed clients read
  `NVIDIA_API_KEY`. Phase 4 unifies (accept both, prefer `NVIDIA_API_KEY`)
  so the agent router and OppFeed share one key.
- **Finding:** `.opencode/` does not exist in the working tree — the
  no-terminal rule is already satisfied; Phase 8's preflight scripts the
  check so it fails fast if it ever appears.
- `mock`/`opencode_cli` live in OppFeed's own `LLM_PROVIDER_CHAIN`; they are
  NOT part of the agent-tooling `ALLOWED_PROVIDERS` (telemetry jobs).

### Phase 1 — MCP core contract — DONE (commit `98d1bad`)
- `backend/app/mcp/core/registry.py` — tool registry: subsection scoping, 5 s per-call timeout, 10 000-row cap, mandatory `ToolCallAudit` row on success/refusal/timeout/crash.
- `backend/app/mcp/core/queries.py` — `assert_read_query` (write-keyword regex + credential-table fragments `auth_`/`token`/`password_hash` refused before anything reaches the engine), `ToolNotPermitted`.
- `backend/app/llms/__init__.py` — free-only provider router; a paid provider name is refused even with a working key in env.
- Suite-wide invariant hardened: **every Postgres connection starts core-first** (`search_path=core,academic,social,telemetry,public` in `engine_kwargs`), ending the pooled-connection search-path accidents; `test_mcp_core.py` 10 tests.

### Phase 2 — Monitoring MCP & in-app collectors — DONE (commit `bc32586`)
- `backend/app/observability/host.py` — psutil host metrics in-process (replaces node-exporter + cAdvisor): deltas, first-sample None, reboot-safe counters, per-metric failure isolation. `psutil` also added to `backend/requirements.txt` (was silently missing and crashed `features/health` in clean installs).
- `backend/app/observability/uptime.py` — reader-derived uptime from `health_metric` sample coverage (replaces blackbox): gap counting, bootstrap anchoring, None-vs-0 honesty.
- `backend/app/mcp/monitoring/` — tools `health_latest`, `health_uptime_pct`, `daily_active_users` on the Phase 1 registry.
- `thresholds.py` source labels repointed to the actual stores (`health_metric`, `psutil`); A-W collector derives uptime from coverage; telemetry Mirrors kept green — 778 passed / 2 known pre-existing (documented, Phase 10-gated).
- Parity rows 1–3 and 6–8: implemented, 7-day gate running (table below).

### Phase 3 — Egress gate: redaction & pseudonymization — PENDING (next)
Owns prompt tasks 1 + 2 and the egress-gate core (architecture rule 2).

- `backend/app/mcp/core/redact.py`
  - `redact(text) -> str`: regex-mask emails, JWT-shaped tokens, phone numbers, IP addresses, `password`/`_hash` field values, card-like numbers (Luhn-shaped run).
  - `pseudonymize_id(value, salt) -> "USER_xxxxxxxx"`: SHA-256 truncated, stable within one run so the model can count recurrences without learning identities; salt is per-run random and kept in audit metadata.
- **Wiring at exactly ONE call site:** the shared `ToolResult` assembly in `mcp/core/registry.py` — every registered tool (including `mcp/monitoring/*` and future aggregate tools) inherits it; `queries.py`-based read paths and the monitoring tool output dicts are covered because they all return through `run_tool`. Byte counts of redactions feed `redactions_applied` once the Phase 4 columns land.
- Row cap for LLM-bound contexts: 50 rows per call; group-question tools (Phase 5) return aggregates instead of rows.
- Tests: per pattern + unicode/case/format edges; **planted email/JWT/phone/IP in source DB rows can never appear in any tool output** (capture + assert).

Verify: redaction unit tests green; planted-PII integration test green; all existing test files untouched and green.

### Phase 4 — Provider routing, job-kind gating & LLM egress auditing — PENDING
Owns prompt tasks 4 (incl. reuse of the OppFeed LLM client) + architecture rules 1, 2, 10.

- Config (`app/core/config.py`, no hard-coding): `llm_provider ∈ {nvidia_nim, openrouter, ollama}` + `llm_model`. Reconcile with the existing generic `llm_provider`/"openai-compatible" settings: `llm_base_url`/`llm_api_key` stay as plumbing, but the *named* provider must be on `ALLOWED_PROVIDERS = {nvidia_nim, openrouter, ollama}`; `off` remains a valid "no LLM" value. The NVIDIA env key is unified with OppFeed's (`NVIDIA_API_KEY` accepted, `NVIDIA_NIM_API_KEY` as alias) per the Phase 0 re-run finding.
- Startup validation in the scan worker path: provider outside the allowlist → that job refuses to start; `job_kind=telemetry` without verified redaction wiring (the Phase 3 self-check) → refuses with a clear error, **no request sent**.
- `job_kind ∈ {telemetry, public_data}` routing: telemetry jobs pass through the egress gate; `public_data` (OppFeed) uses any allowlisted provider freely. **REUSE the existing OppFeed provider clients** (`features/oppfeed` NVIDIA NIM / OpenRouter request plumbing) rather than a second parallel LLM stack; `llms/` remains the single allowlist surface and re-exports the OppFeed clients.
- Alembic migration: `tool_call_audit` gains `sent_to` (which provider consumed what), `redactions_applied` (count), `bytes_out` (redacted payload size), `redaction_salt` (per-run random). Every outbound LLM request writes a row.

Verify: provider-outside-allowlist → config rejected; telemetry job with redaction unwired → startup error, zero network attempts; audit rows present with the new columns; e2e request capture contains no planted PII.

### Phase 5 — Aggregate tool layer & scan-agent runtime — PENDING
Owns prompt task 3 + task 5.

- Curated aggregate tools (registry-registered, read-only, 5 s timeouts, counts/summaries **only** — never raw rows, emails, tokens):
  `failed_logins_by_hour`, `feedback_themes_top5`, `p95_latency_window`, `crash_clusters(max_n)`, `telemetry_health(days)`, `security_signals(days)` (crash-monitor equivalents). README table per tool: name, params, and an explicit "what it never returns" column; enforced by the Phase 3 egress gate + planted-PII test.
- Scan-agent runtime: calls §3 tools → receives the SCAN-AGENT.md §1 system prompt → fills the §2 `ScanResult` schema → **real `reconcile()`** (upgrade the current `_reconcile_findings` stub: re-query every cited `metric_key` from the audit trail, >2 % deviation fails the scan) → retries once at lower temperature → stores subsection as `error`, never faked healthy.
- No auto-act on tool output anywhere; feeds the UI as display-only until Phase 6 wires the executor.

Verify: reconcile catches a deliberately wrong cited number (test); clean DB scan returns healthy, not error; curated tools answer the A/W+B subsections' needs.

### Phase 6 — Reactive safety: propose-not-execute reactor — PENDING
Owns prompt task 3's executor half (architecture rule 4).

- `backend/app/mcp/reactor/` — enum action → procedure map (idempotent, logged, deterministic); every proposal invocation writes `tool_call_audit` with `proposed/executed/rejected`, `sent_to`, `redactions_applied`, `bytes_out`.
- Non-enum action → rejected + logged; the model never executes.

Verify: executor rejects a non-enum action (test); audit row exists for every proposal; idempotency asserted per procedure.

### Phase 7 — Isolation: compose networks, secrets split, RBAC endpoint — PENDING
Owns prompt decisions 5–8 and task 7.

- `docker-compose.yml`: `edge` and `app-internal (internal: true)` networks; agent/scan services on internal except the single minimal egress path (LLM-client semantics only); Prometheus/Grafana stay off the edge while Phase 10 is pending.
- Agent containers receive ONLY provider keys + the restricted read-only DB role (dedicated role over the `SQL_ALLOWLIST` tables); `.env` only in the backend container; ollama kept but unexposed and unused by any job.
- Optional HTTP MCP endpoint behind `ENABLE_ADMIN_MCP=false` default + `get_current_user` admin gate middleware (student tokens → empty tool list).

Verify: `docker compose config` shows the networks + internal flag; agent env contains no `SECRET_KEY`/`SMTP_*`; admin middleware denies student tokens.

### Phase 8 — Preflight CI gate & image hygiene — PENDING
Owns prompt task 8.

- `scripts/preflight.py` — non-zero exit on any failure, one-line report per check:
  terminal/shell MCP reachable from prod config → FAIL · `ENABLE_ADMIN_MCP=true` in prod → FAIL · agent env contains `SECRET_KEY`/SMTP/unrelated keys → FAIL · telemetry job without redaction wiring → FAIL · provider outside allowlist on any job → FAIL · `.opencode` in the built backend image → FAIL · agent DB user not read-only-restricted → FAIL · Prometheus/Grafana exposed on edge → FAIL · egress-audit rows missing after a test scan → FAIL.
- Backend image excludes `.opencode/`.

Verify: preflight passes on this repo; `docker run --rm <backend-image> ls .opencode` fails.

### Phase 9 — Docs, ADR & recorded demo — PENDING
Owns prompt task 9 + final acceptance.

- `README.md`: new env vars, provider routing, preflight usage.
- `docs/observability/SCAN-AGENT.md` §4 gains the egress-gate rule ("every response redacted before entering context; raw rows never sent").
- ADR note at docs top: hosted-free-OSS chosen by operator decision; local fallback (ollama, optional/disabled) available but not required.
- Record ONE end-to-end demo scan: subsection filled, audit rows show provider = nvidia_nim, `bytes_out` = redacted payload size.

### Phase 10 — Legacy removal (v1 parity gate, UNCHANGED) — GATED
Directive 1. All 7 monitoring containers deleted + 3 volumes in ONE commit, only after the parity table below passes for a full 7-day parity week, and only while preflight keeps guarding the edge. Rollback = revert commit.

---

## Parity checklist (the Phase 10 deletion gate)

Status: `pending` → `implemented (7-day gate running)` → `verified`. Rows 1–3/6–8 are being fed by the in-app stores since Phase 2; nothing is deleted until every row is `verified`.

| # | Requirement | Current owner | MCP owner | Status |
|---|-------------|---------------|-----------|--------|
| 1 | p95 latency finding | thresholds.py | health_metric (in-app histogram deltas) | implemented (Phase 2) — gate running |
| 2 | HTTP 5xx-rate finding | thresholds.py | health_metric (in-app HTTP mix) | implemented (Phase 2) — gate running |
| 3 | DB query p95 finding | thresholds.py | health_metric (in-app histogram deltas) | implemented (Phase 2) — gate running |
| 4 | 8 subsection ScanResult verdicts | telemetry.scan_result | analyst MCP (Phase 5 runtime) | pending |
| 5 | Incident transitions | telemetry.status_transition | monitoring MCP | pending |
| 6 | Tool-call audit + reconciliation | telemetry.tool_call_audit | mcp/core (Phases 1+5) | implemented — gate running |
| 7 | Host CPU/RAM/disk/net | node_exporter + cadvisor | psutil via observability/host | implemented (Phase 2) — gate running |
| 8 | Uptime probes | blackbox-exporter | reader-derived coverage (observability/uptime) | implemented (Phase 2) — gate running |
| 9 | Alert routing + silencing | alertmanager | alerting MCP + SMTP | pending |
| 10 | Dashboards | grafana | admin UI | pending |

## Free-forever gate (unchanged)

No paid API, no trial-expiring service, no free-tier-that-bills-later dependency.
Allowed: NVIDIA NIM (primary), OpenRouter (`:free` models, fallback), ollama
(optional disabled local fallback), existing Gmail SMTP. Anything else needs
owner sign-off. Every new dependency: open-source, merged into the bundle,
justified for size (psutil, prometheus_client already carried this bar).

## Working rules (carried forward)

- Dormant-by-default: new agent code is imported only by tests, the scan worker, and preflight — never by `main.py` or live request paths.
- SQLModel patterns per AGENTS.md: `session.exec(select(...))`, server-side timestamp defaults, Alembic for schema changes.
- Never commit `.env`, `database/classpilot.db`, `uploads/`, `.opencode/` edits.
- Pre-PR: `pytest tests/ -q` green; frontend build/lint/tsc green if touched.

## Acceptance criteria (v2)

- [ ] Failure mode: telemetry job with redaction unwired → clear startup error, NO request sent.
- [ ] Planted email/JWT/phone/IP in DB can never appear in any tool output or LLM request body (asserted on captured requests).
- [ ] Provider outside allowlist → config rejected at startup.
- [ ] `reconcile()` catches a deliberately wrong cited number (test).
- [ ] Executor rejects non-enum action; audit row exists for every proposal.
- [ ] `docker compose config` shows required networks + internal flag.
- [ ] `docker run --rm <backend-image> ls .opencode` fails (dev files absent).
- [ ] `scripts/preflight.py` passes on this repo.
- [ ] One end-to-end demo scan recorded: subsection filled, audit rows show provider = nvidia_nim, `bytes_out` = redacted payload size.
- [ ] All new + existing tests green; README and SCAN-AGENT.md updated.
