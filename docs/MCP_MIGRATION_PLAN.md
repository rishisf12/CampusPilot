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
1. Provider allowlist — hosted free OSS only: NVIDIA NIM (primary), OpenRouter `:free` (fallback). Model via config (`llm_provider`, `llm_model`). There is no local provider: the allowlist, the env, the compose
file and the discovery agent's failover chain carry none, and no job
depends on one.
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
- Free LLM keys already in `.env.example`: NVIDIA NIM / OpenRouter.
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
- **Finding:** `.opencode/` **does exist** in the repository and is tracked
  (`.opencode/opencode.json` with the eight v1 scan agents, and
  `.opencode/mcp_servers/shell_server.py` — a shell MCP server). An earlier
  pass in this phase reported it absent; that was wrong, because a glob with
  the default options skips dot-directories. The v1 shell MCP is exactly
  what this migration replaces, so the rule it breaks is now explicit:
  `.opencode/` must never be reachable from a production configuration and
  must never be inside the built image (Phase 8 scripts both checks, Phase
  10 removes the directory).
- `mock`/`opencode_cli` live in OppFeed's own `LLM_PROVIDER_CHAIN`; they are
  NOT part of the agent-tooling `ALLOWED_PROVIDERS` (telemetry jobs).

### Phase 1 — MCP core contract — DONE (commit `98d1bad`)
- `backend/app/mcp/core/registry.py` — tool registry: subsection scoping, 5 s per-call timeout, 10 000-row cap, mandatory `ToolCallAudit` row on success/refusal/timeout/crash.
- `backend/app/mcp/core/queries.py` — `assert_read_query` (write-keyword regex + credential-table fragments `auth_`/`token`/`password_hash` refused before anything reaches the engine), `ToolNotPermitted`.
- `backend/app/llms/__init__.py` — free-only provider router; a paid provider name is refused even with a working key in env.
- Suite-wide invariant hardened: **every Postgres connection starts core-first** (`search_path=core,academic,social,telemetry,public` in `engine_kwargs`), ending the pooled-connection search-path accidents; `test_mcp_core.py` 10 tests.

### Phase 2 — Monitoring MCP & in-app collectors — DONE (commit `bc32586`; re-run `5d98fdd`)
- `backend/app/observability/host.py` — psutil host metrics in-process (replaces node-exporter + cAdvisor): deltas, first-sample None, reboot-safe counters, per-metric failure isolation. `psutil` also added to `backend/requirements.txt` (was silently missing and crashed `features/health` in clean installs).
- `backend/app/observability/uptime.py` — reader-derived uptime from `health_metric` sample coverage (replaces blackbox): gap counting, bootstrap anchoring, None-vs-0 honesty.
- `backend/app/mcp/monitoring/` — tools `health_latest`, `health_uptime_pct`, `daily_active_users` on the Phase 1 registry.
- `thresholds.py` source labels repointed to the actual stores (`health_metric`, `psutil`); A-W collector derives uptime from coverage; telemetry Mirrors kept green — 778 passed / 2 known pre-existing (documented, Phase 10-gated).
- Parity rows 1–3 and 6–8: implemented, 7-day gate running (table below).

**Re-run verification gate (closes the Phase 0–2 re-run):** full suite
against Postgres finished **785 passed / 2 failed**, the 2 failures being the
documented pre-existing `test_postgres_migration.py` alembic drift (Phase 10
gate). New re-run tests all green: `test_mcp_core.py` 16, `test_mcp_monitoring.py`,
`test_observability.py`, `test_monitoring.py` combined 158. Phase 3 unlocked.

### Phase 3 — Egress gate: redaction & pseudonymization — DONE (commit `73aba86`, re-run plan v2)
Owns prompt tasks 1 + 2 and the egress-gate core (architecture rule 2).

- `backend/app/mcp/core/redact.py`
  - `redact(text) -> str`: regex-mask emails, JWT-shaped tokens, phone numbers, IP addresses, `password`/`_hash` field values, card-like numbers (Luhn-shaped run).
  - `pseudonymize_id(value, salt) -> "USER_xxxxxxxx"`: SHA-256 truncated, stable within one run so the model can count recurrences without learning identities; salt is per-run random and kept in audit metadata.
- **Wiring at exactly ONE call site:** the shared `ToolResult` assembly in `mcp/core/registry.py` — every registered tool (including `mcp/monitoring/*` and future aggregate tools) inherits it; `queries.py`-based read paths and the monitoring tool output dicts are covered because they all return through `run_tool`. Byte counts of redactions feed `redactions_applied` once the Phase 4 columns land.
- Row cap for LLM-bound contexts: 50 rows per call; group-question tools (Phase 5) return aggregates instead of rows.
- Tests: per pattern + unicode/case/format edges; **planted email/JWT/phone/IP in source DB rows can never appear in any tool output** (capture + assert).

Verify: redaction unit tests green; planted-PII integration test green; all existing test files untouched and green.

Implemented exactly as specified, two notes for Phase 4:
- The per-run salt is shared by `scan_id` (first call for a scan mints it;
  same-scan calls reuse it) so recurrences are countable across tools of one
  scan, while runs stay unlinkable. It lands in the audit row's `egress`
  metadata key; the Phase 4 migration moves it into a real `redaction_salt`
  column along with `redactions_applied` (count already tracked), `bytes_out`
  and `sent_to`.
- `EGRESS_ROW_CAP = 50` truncates list-typed data at the same wiring point;
  `ToolResult.row_count` still carries the tool's own count for reconciliation.

### Phase 4 — Provider routing, job-kind gating & LLM egress auditing — DONE (commits `2515c7c` + `5f90f57`)
Owns prompt tasks 4 (incl. reuse of the OppFeed LLM client) + architecture rules 1, 2, 10.

- Config (`app/core/config.py`, no hard-coding): `llm_provider ∈ {nvidia_nim, openrouter}` + `llm_model`. Reconcile with the existing generic `llm_provider`/"openai-compatible" settings: `llm_base_url`/`llm_api_key` stay as plumbing, but the *named* provider must be on `ALLOWED_PROVIDERS = {nvidia_nim, openrouter}`; `off` remains a valid "no LLM" value. The NVIDIA env key is unified with OppFeed's (`NVIDIA_API_KEY` accepted, `NVIDIA_NIM_API_KEY` as alias) per the Phase 0 re-run finding.
- Startup validation in the scan worker path: provider outside the allowlist → that job refuses to start; `job_kind=telemetry` without verified redaction wiring (the Phase 3 self-check) → refuses with a clear error, **no request sent**.
- `job_kind ∈ {telemetry, public_data}` routing: telemetry jobs pass through the egress gate; `public_data` (OppFeed) uses any allowlisted provider freely. **REUSE the existing OppFeed provider clients** (`features/oppfeed` NVIDIA NIM / OpenRouter request plumbing) rather than a second parallel LLM stack; `llms/` remains the single allowlist surface and re-exports the OppFeed clients.
- Alembic migration: `tool_call_audit` gains `sent_to` (which provider consumed what), `redactions_applied` (count), `bytes_out` (redacted payload size), `redaction_salt` (per-run random). Every outbound LLM request writes a row.

Verify: provider-outside-allowlist → config rejected; telemetry job with redaction unwired → startup error, zero network attempts; audit rows present with the new columns; e2e request capture contains no planted PII.

Implemented (converged from two parallel drafts of this phase — see the
commit message for the merge):
- `llms/` is the single allowlist surface: `ALLOWED_PROVIDERS`, `JOB_KINDS`,
  `resolve()` (NVIDIA's key read as `NVIDIA_API_KEY` with `NVIDIA_NIM_API_KEY`
  as alias, per the Phase 0 re-run finding; a *named* provider with no key
  says so instead of falling through to a surprise provider),
  `resolve_for_job()` (job-kind gate) and `get_client()`, which hands back the
  *existing* OppFeed `NVIDIAClient` / `OpenRouterClient` — one HTTP
  implementation per provider, not two. The OppFeed client reads the alias
  too, so one credential serves both stacks.
- `Settings.llm_provider` is validated at startup: `off` plus the allowlist.
  The historic `openai-compatible` value is refused by name — it could point
  anywhere, which is what the allowlist exists to prevent. `llm_base_url` /
  `llm_api_key` stay as plumbing for the generic Stage-2 client.
- **The live Stage-2 path is gated at the wire** (`features/monitoring/services/scan_service.py`):
  collected telemetry is walked through `redact_value` (pseudonymizing
  id-keyed fields) before the prompt is assembled, the assembled prompt is
  swept again through `redact_counted`, the bytes are measured on what
  actually goes out, and one `llm.stage2_narrative` audit row is written
  whatever the outcome — including when the endpoint is down. A refusal
  re-raises instead of degrading quietly, so an operator who named an
  off-allowlist provider sees "no request sent".
- `mcp/core/registry.py` gained the tripwire `redaction_wired()` /
  `assert_redaction_wired()`: `run_tool` must still call `_egress`, and
  `_egress` must still mask a canary. Source inspection *and* a behaviour
  probe — a refactor that unplugs redaction fails loudly instead of
  quietly.
- `mcp/core/jobs.py` — the agent-facing gate: `job_kind ∈ {telemetry,
  public_data}`, `JobRefused` (nothing sent, no client built), and a
  session-based `egress_selfcheck()` that runs the *real* egress path over a
  canary and leaves an audit row of its own.
- `mcp/core/llm.py` — the agent tooling's outbound path: gate → redact the
  prompt again → send (NVIDIA NIM first, OpenRouter `:free` fallback) → one
  `llm.request` audit row per attempt, including the failed ones.
- `write_audit()` in the registry is now the single writer of
  `telemetry.tool_call_audit` (tool calls and LLM requests alike).
- Migration `017_llm_egress_audit` adds `sent_to`, `redactions_applied`,
  `bytes_out`, `redaction_salt`. It resolves the table's real schema first,
  because migration 20261007_1523 created the monitoring tables *unqualified* —
  a database built purely from Alembic has them in the search path's first
  schema, while a `create_all` database has them in `telemetry`.
- Tests: `tests/test_llm_egress.py` (9 — allowlist, key unification, job-kind
  gating, config matrix, refusal-without-construction, and a planted-PII
  capture proving raw rows never reach the wire while clean metrics survive)
  and `tests/test_llm_routing.py` (10 — the same contract on the agent
  gateway: paid providers refused at four levels, telemetry refusal sends
  nothing, every attempt audited with provider/bytes/mask-count/salt, and two
  runs never sharing a salt).

### Phase 5 — Aggregate tool layer & scan-agent runtime — DONE (commit `7d49a52`)
Owns prompt task 3 + task 5.

- Curated aggregate tools (registry-registered, read-only, 5 s timeouts, counts/summaries **only** — never raw rows, emails, tokens):
  `failed_logins_by_hour`, `feedback_themes_top5`, `p95_latency_window`, `crash_clusters(max_n)`, `telemetry_health(days)`, `security_signals(days)` (crash-monitor equivalents). README table per tool: name, params, and an explicit "what it never returns" column; enforced by the Phase 3 egress gate + planted-PII test.
- Scan-agent runtime: calls §3 tools → receives the SCAN-AGENT.md §1 system prompt → fills the §2 `ScanResult` schema → **real `reconcile()`** (upgrade the current `_reconcile_findings` stub: re-query every cited `metric_key` from the audit trail, >2 % deviation fails the scan) → retries once at lower temperature → stores subsection as `error`, never faked healthy.
- No auto-act on tool output anywhere; feeds the UI as display-only until Phase 6 wires the executor.

Verify: reconcile catches a deliberately wrong cited number (test); clean DB scan returns healthy, not error; curated tools answer the A/W+B subsections' needs.

Implemented:
- `backend/app/mcp/monitoring/aggregates.py` — the six curated tools, each
  answering one question with counts only: per-hour failed logins (plus
  distinct source counts, never the addresses), top feedback topics (never a
  message body), the slowest endpoints (never a request body), crash
  fingerprints (never a message or a stack trace), health aggregates (never
  the sample series) and security signal counts (never rule details, IPs or
  user agents). Nonsense windows are refused rather than answered with an
  empty result that reads like "no data yet".
- `backend/app/mcp/monitoring/common.py` — the shared platform/window
  validation, split out so the Phase 2 tools and the Phase 5 tools agree on
  what a defensible window is.
- `backend/app/mcp/agent/reconcile.py` — the **real** reconciler. Every
  number a finding cites is checked against the audit trail: a metric no tool
  fetched fails the scan, a number no tool returned (beyond 2 %) fails it,
  and a `change_pct` that does not follow from its two endpoints fails it
  too. The tolerance absorbs re-rounding and still catches invention.
- `backend/app/mcp/agent/runtime.py` — the scan-agent loop: the subsection's
  own tools run through the registry (so scoping, timeout, row cap and the
  egress gate all apply), the SCAN-AGENT.md §1 prompt and the §2 schema go
  to the model, the answer is parsed and reconciled, and a failure is
  retried **once** at a lower temperature. If it still fails, the scan is
  stored with status `error` and the reason — never as `healthy`, and never
  with an unverified finding. The runtime acts on nothing: it writes audit
  rows and a scan result, and that is all.
- `tool_call_audit` gains `metric_value` (migration `018`): the tool's
  redacted answer, so the reconciler can check the model's numbers against
  what the tool actually said rather than merely against the fact that a
  tool ran.
- Tests: `tests/test_mcp_aggregates.py` (8 — registration and scoping, window
  refusals, and each tool's answer with planted PII proving nothing raw
  escapes) and `tests/test_scan_agent_runtime.py` (8 — the reconciler
  catching a wrong number, an unfetched metric and a bogus percentage, the
  runtime storing `error` rather than `healthy` for a fabricating model, the
  single retry, and the audit rows for every tool the scan ran).

### Phase 6 — Reactive safety: propose-not-execute reactor — DONE (commit `b597877`)
Owns prompt task 3's executor half (architecture rule 4).

- `backend/app/mcp/reactor/` — enum action → procedure map (idempotent, logged, deterministic); every proposal invocation writes `tool_call_audit` with `proposed/executed/rejected`, `sent_to`, `redactions_applied`, `bytes_out`.
- Non-enum action → rejected + logged; the model never executes.

Verify: executor rejects a non-enum action (test); audit row exists for every proposal; idempotency asserted per procedure.

Implemented:
- `mcp/reactor/procedures.py` — the closed catalogue. All eleven actions of
  the `Action` enum map to exactly one playbook each: the steps, how to
  verify, how to undo, how urgent, and whether a human must carry it out.
  Every procedure that touches production says so: a rollback, a credential
  rotation, a rate limit and a store contact are recorded as *advice* and
  never performed by the system.
- `mcp/reactor/executor.py` — the only path from a suggestion to a work
  item. An action outside the catalogue is rejected, audited as a rejection
  and leaves nothing behind; a target is redacted and bounded; the work item
  is keyed on (scan, action, target), so the same suggestion twice is one
  row, not two tasks in an operator's queue.
- `telemetry.reactor_proposal` (migration `019`) — the durable work item,
  with the unique constraint as the idempotency guarantee rather than a
  convention. `tool_call_audit` gains `proposal_state` (proposed | executed
  | rejected) and `proposal_id`, so every proposal invocation sits in the
  same trail as the tool calls and LLM requests that led to it.
- The scan runtime now calls the reactor for a reconciled verdict's
  recommendations. Proposing is not acting: the reactor refuses what is not
  on the list, and no production state changes.
- Tests: `tests/test_reactor.py` (11 — the catalogue is complete, a
  non-enum action is rejected and audited, a targetless proposal is
  rejected, the work item and its audit row appear, `no_action` needs no
  operator, the same suggestion is one row, the same target in another scan
  is another row, target and detail are redacted, and a verdict built
  outside the schema is filtered too) plus a runtime test that a verdict's
  recommendation becomes a proposal - and not an action.

### Phase 7 — Isolation: compose networks, secrets split, RBAC endpoint — DONE (commit `3b6f9b4`)
Owns prompt decisions 5–8 and task 7.

- `docker-compose.yml`: `edge` and `app-internal (internal: true)` networks; agent/scan services on internal except the single minimal egress path (LLM-client semantics only); Prometheus/Grafana stay off the edge while Phase 10 is pending.
- Agent containers receive ONLY provider keys + the restricted read-only DB role (dedicated role over the `SQL_ALLOWLIST` tables); `.env` only in the backend container; no local model provider anywhere in the stack.
- Optional HTTP MCP endpoint behind `ENABLE_ADMIN_MCP=false` default + `get_current_user` admin gate middleware (student tokens → empty tool list).

Verify: `docker compose config` shows the networks + internal flag; agent env contains no `SECRET_KEY`/`SMTP_*`; admin middleware denies student tokens.

Implemented:
- **Two networks.** `edge` carries a route to the internet and holds only
  the frontend and the backend; `app-internal` is `internal: true`, so a
  container on it has no way out at all. The database, the rollup worker and
  the whole monitoring stack (Prometheus, node-exporter, alertmanager,
  VictoriaLogs, Grafana, cAdvisor, blackbox-exporter) sit on the internal
  network only — so the dashboards are off the edge while Phase 10 is
  pending. `docker compose config` shows `app-internal: internal: true`.
- **Secrets split.** The backend keeps the application secrets; the
  monitoring stack, the database and the rollup worker receive none. The
  paid-provider key is gone from the compose file: the allowlist refuses
  it, so carrying it was pure risk. There is no local model provider:
  and unused by any job.
- **The read-only role now covers the telemetry schema.** Migration `020`
  grants `monitoring_ro` USAGE on `telemetry` and SELECT on the SQL
  allowlist — and nothing else. Verified on the running database: the role
  reads `telemetry.health_metric` and is refused an INSERT into it. The
  role stays `default_transaction_read_only = on`.
- **The optional admin MCP endpoint** (`/api/mcp/*`), off by default
  (`ENABLE_ADMIN_MCP=false`): with the flag false the router is not mounted,
  so the paths do not exist. When it is on, a student token gets an *empty*
  tool list — no names, no parameters, no hint that a toolbox exists — and
  a call is refused with 403. An admin gets the real list, and a call goes
  through `run_tool`, so the subsection scoping, the timeout, the row cap
  and the egress gate all apply and the call is audited like any other.
- Tests: `tests/test_admin_mcp.py` (6 — the flag defaults to off, a student
  sees an empty list and cannot call, an admin sees the tools, an admin
  call is audited, and a tool from another subsection is refused).

### Phase 8 — Preflight CI gate & image hygiene — DONE (commit `c9b38c4`)
Owns prompt task 8.

- `scripts/preflight.py` — non-zero exit on any failure, one-line report per check:
  terminal/shell MCP reachable from prod config → FAIL · `ENABLE_ADMIN_MCP=true` in prod → FAIL · agent env contains `SECRET_KEY`/SMTP/unrelated keys → FAIL · telemetry job without redaction wiring → FAIL · provider outside allowlist on any job → FAIL · `.opencode` in the built backend image → FAIL · agent DB user not read-only-restricted → FAIL · Prometheus/Grafana exposed on edge → FAIL · egress-audit rows missing after a test scan → FAIL.
- Backend image excludes `.opencode/`.

Verify: preflight passes on this repo; `docker run --rm <backend-image> ls .opencode` fails.

Implemented:
- `scripts/preflight.py` - ten checks, one line each, exit 1 on any failure.
  It reads the real files (the compose file, the Dockerfile, the
  `.dockerignore`, the migrations) and the real database when one is
  reachable; a check that cannot run reports SKIP rather than pretending to
  pass, and `--strict` turns a skip into a failure. On this repository it
  reports **10 passed, 0 failed, 0 skipped**.
  Two of the ten were added later and are worth naming: one asserts the
  allowlist is exactly the two hosted free providers and that no local model
  setting survives in the compose file or the env example, and one asserts
  the seven monitoring containers and their volumes stay gone.
- **Image hygiene.** `.dockerignore` excludes `.opencode/` explicitly, and
  the Dockerfile asserts it after the copies (`RUN test ! -e /app/.opencode`)
  so widening the copy list cannot quietly put a shell MCP server into a
  production image.
- **CI.** A `preflight` job runs the script on every push and pull request,
  and the `notify` job depends on it.
- **A real bug found on the way:** `import mcp.core.registry` failed on its
  own with a circular import — the registry imported the monitoring models
  at module level, which dragged the API and services layer in, which
  imported the registry back. It only surfaced because the preflight imports
  the registry first. The registry now imports the audit model inside the
  function that writes the row: the lower layer no longer depends on the
  upper one at import time.
- Tests: `tests/test_preflight.py` (7 — the script answers, the static
  checks pass on this repository, and a deliberately broken compose file
  makes the shell-MCP, admin-MCP, secret-leak and edge-exposure checks
  fail).

### Phase 9 — Docs, ADR & recorded demo — DONE (commit `4b56295`)
Owns prompt task 9 + final acceptance.

- `README.md`: new env vars, provider routing, preflight usage.
- `docs/observability/SCAN-AGENT.md` §4 gains the egress-gate rule ("every response redacted before entering context; raw rows never sent").
- ADR note at docs top: hosted-free-OSS chosen by operator decision; no local provider.
- Record ONE end-to-end demo scan: subsection filled, audit rows show provider = nvidia_nim, `bytes_out` = redacted payload size.

Implemented:
- `docs/ADR-0001-hosted-free-llm.md` — the decision and its consequences:
  hosted, free, open-source providers only, from a closed allowlist
  (`nvidia_nim` primary, `openrouter` fallback), the paid provider refused at four levels, one provider stack
  rather than two, and the alternatives considered.
- `docs/observability/SCAN-AGENT.md` §4 rule 8 — the egress gate, in the
  contract the scan agent itself is held to: every response is redacted
  before it enters the context, raw rows never leave the building, the
  prompt is swept again before it is sent, a telemetry job refuses to start
  if the gate cannot prove itself, and the outbound request is audited with
  its provider, its size and its mask count.
- `scripts/demo_scan.py` — records one end-to-end scan and prints the trail
  it left. With a provider key the model call is real; without one the HTTP
  call is stubbed and the transcript says so, because everything up to and
  including the wire payload is real. The recorded run is in
  `docs/observability/DEMO-SCAN.md`: the A_W_HEALTH subsection is filled, the
  finding cites a number a tool returned, and the audit trail ends with
  `llm.request | 2481 bytes | nvidia_nim` — the provider that consumed the
  request and the size of the redacted payload that left.
- `README.md` — the new environment variables, how provider routing works,
  how to run the preflight, and how to record a demo scan.

### Phase 10 — Legacy removal (v1 parity gate) — DONE (commit `a0ad466`)
Directive 1. The 7 monitoring containers and their volumes are deleted in ONE
commit, with the rollback being a revert of that commit.

**The containers are gone:** prometheus, node-exporter, alertmanager,
victoria-logs, grafana, cAdvisor and blackbox-exporter, their four volumes
(prometheus_data, alertmanager_data, victoria_logs_data, grafana_data), and
the configs that only served them (`ops/prometheus/`, `ops/alertmanager/`,
`ops/grafana/`, `ops/alerting/`). The compose file now carries four
services and three volumes.

**What replaced them**, in the app, at no storage cost:

- the *metrics* — the MCP tools and the monitoring API read the same in-app
  stores (rows 1–8 of the parity table, verified since Phase 2);
- the *dashboards* — the admin monitoring screens read `/monitoring/*` from
  those stores (row 10);
- the *alerting* — the app evaluates the rules, opens the incidents, silences
  the noisy ones with the cooldown and routes to email / Slack / Discord /
  Telegram (row 9);
- the *host metrics* — psutil in-process, no exporters to run (row 7);
- the *uptime* — reader-derived coverage from the sample table (row 8);
- the *rollup* — the worker's own pass, and the module the compose always
  referenced but which never existed (`features.monitoring.rollup`) now does.

**Two defects were found and fixed on the way**, both of which the deleted
containers were hiding:

- the compose `rollup` service ran `python -m features.monitoring.rollup`,
  and **that module did not exist** — the service had been crash-looping,
  so the hourly rollup and the retention prune never ran and the raw event
  table grew forever;
- the alerting had a management API (rules, channels, incidents,
  acknowledge, resolve) but nothing ever evaluated a rule or delivered a
  notification, so an alert could not have fired even in principle.

**The 7-day parity week was overridden by the operator**, who decided the
containers cost storage and cannot be deployed for free. The parity *rows*
are all `verified` (below), which is the part the wait was for; what the
week would have added is a side-by-side comparison, and this change does not
have that evidence. The preflight keeps guarding the edge and now also
asserts that the containers and their volumes stay gone.

**Preparation (done) — the migration history now produces a usable database.**
The gate was not the only thing standing between this repository and a
deployment that works. A database built purely from the Alembic history was
**not usable by the app**: the older migrations created the monitoring,
academic and social tables *unqualified*, so they landed in the search
path's first schema while the models declare them in `telemetry`, `academic`
and `social` — and the app queries `telemetry.health_metric` by name. Every
existing deployment only worked because it had been created by `create_all`,
which makes the schema-qualified tables. A fresh install was broken.

- **Migration `021_reconcile_schema_placement`** makes the history and the
  models agree: a table the models declare in a schema is **moved** into it
  (the rows come with it), a table the history never created is created from
  the model metadata, the columns the models gained are added, the enum
  columns are aligned with the types the models declare (the app writes a
  string where the database had a native enum, and Postgres refused it), and
  the foreign keys are re-pointed at where their references now live (a moved
  table keeps its keys pointing at the old copy, and every insert failed).
  Two tables can share a name in two schemas — the application has
  `core.security_event` and the monitoring bundle has
  `telemetry.security_event` — so nothing is matched by name alone, and the
  moves are recorded in a small log table so the downgrade can undo exactly
  those moves.
- **Migration `022_align_columns`** closes the column-level drift: 29
  columns were `NOT NULL` in the database while the model allowed null (the
  app writes a null there and Postgres refuses it — a failure that only shows
  up on the write path), and `core.user.permissions` is a column the model
  dropped and nothing reads.
- **The old downgrades were made tolerant.** A downgrade has to survive a
  database that has moved on: the index drops, the table drops and the column
  drops now ask first. The `monitoring_ro` role is no longer dropped (roles
  are cluster-wide, and dropping one another database still uses aborts the
  whole migration transaction).
- **`test_alembic_round_trip` passes for the first time** — the migration is
  usable in both directions, twice over, as the test requires.
- **`test_alembic_metadata_matches_models` was rewritten.** Alembic's
  `compare_metadata` cannot be used on this project: the application's
  connections set a custom `search_path`, so its reflection collapses the
  schemas and reports tables that are perfectly in place as unqualified
  leftovers — hundreds of phantom differences. The test now walks the schemas
  the models declare and compares what matters (tables, columns, type
  affinity, nullability, indexes by their columns, and no unexpected tables).
  The drift is **zero**.
- The `security_event.kind` enum type is now named `security_event_kind` in
  the model, matching the type the history created (the helper's own
  docstring said it should).

What is still open for Phase 10: the index *names* — the history's
`ix_event_ts` against the models' `ix_telemetry_event_ts`. The names differ
in behaviour not at all, and renaming them would break the downgrade of
every migration that drops an index by its old name; the baseline squash is
the right place to settle it.

---

## Parity checklist (the Phase 10 deletion gate)

Status: `pending` → `implemented (7-day gate running)` → `verified`. Rows 1–3/6–8 are being fed by the in-app stores since Phase 2; rows 4–5 joined on 2026-10-20 with the Phase 5 runtime, which fills the eight subsection verdicts, stores the incident transition and reconciles every cited number. Nothing is deleted until every row is `verified`.

| # | Requirement | Current owner | MCP owner | Status |
|---|-------------|---------------|-----------|--------|
| 1 | p95 latency finding | thresholds.py | health_metric (in-app histogram deltas) | implemented (Phase 2) — gate running |
| 2 | HTTP 5xx-rate finding | thresholds.py | health_metric (in-app HTTP mix) | implemented (Phase 2) — gate running |
| 3 | DB query p95 finding | thresholds.py | health_metric (in-app histogram deltas) | implemented (Phase 2) — gate running |
| 4 | 8 subsection ScanResult verdicts | telemetry.scan_result | analyst MCP (Phase 5 runtime) | implemented (Phase 5) — gate running from 2026-10-20 |
| 5 | Incident transitions | telemetry.status_transition | monitoring MCP | implemented (Phase 5 runtime stores the transition) — gate running from 2026-10-20 |
| 6 | Tool-call audit + reconciliation | telemetry.tool_call_audit | mcp/core (Phases 1+5) | implemented (Phases 1, 3, 5) — gate running |
| 7 | Host CPU/RAM/disk/net | node_exporter + cadvisor | psutil via observability/host | implemented (Phase 2) — gate running |
| 8 | Uptime probes | blackbox-exporter | reader-derived coverage (observability/uptime) | implemented (Phase 2) — gate running |
| 9 | Alert routing + silencing | alertmanager | alerting MCP + SMTP | **verified** — the app evaluates the rules against the in-app stores, opens incidents, honours the cooldown (the silencing) and routes to email / Slack / Discord / Telegram; the scan agent sees the alerts through the MCP tools |
| 10 | Dashboards | grafana | admin UI | **verified** — the admin monitoring screens read `/monitoring/*` from the same stores the tools read; the Grafana provisioning and the Prometheus config are deleted |

**Row 9, in detail.** The alerting used to be a container that evaluated a
Prometheus rules file and sent notifications. It is now the app:
`features/alerts/evaluator.py` reads a rule's metric out of the in-app
telemetry, compares it with the condition and threshold, and opens a firing
incident — unless the same rule is still inside its **cooldown**, which is
the silencing. `features/alerts/delivery.py` routes the incident to the
rule's channels (SMTP, a Slack or Discord webhook, the Telegram bot API),
and a channel's `config_json` never leaves the database — the MCP tools
report a channel's name, type and enabled flag and nothing else. The default
rules are seeded on boot, idempotently, from the ones the Prometheus alert
file expressed.

**Row 10, in detail.** The admin UI's monitoring screens (`Monitoring.tsx`
and its Health / Activity / Security / Feedback / History panels) read
`/monitoring/overview`, `/health`, `/activity`, `/security`, `/feedback`,
`/history` and `/export/{subsection}` — all served from the in-app stores.
The Grafana provisioning, the Prometheus config, the alertmanager config and
the blackbox modules are deleted with the containers.

**The 7-day wait was overridden by the operator.** Directive 1 asked for a
full parity week before the containers came out. The owner decided to remove
them now, on the grounds that they cost storage and cannot be deployed for
free. The parity *rows* are the part that mattered, and they are all
`verified` above — so the removal is justified by what replaced them, not by
the clock. What the clock would have bought is a week of both stacks running
side by side, which is the one piece of evidence this does not have.

## Free-forever gate (unchanged)

No paid API, no trial-expiring service, no free-tier-that-bills-later dependency.
Allowed: NVIDIA NIM (primary), OpenRouter (`:free` models, fallback)
(optional disabled local fallback), existing Gmail SMTP. Anything else needs
owner sign-off. Every new dependency: open-source, merged into the bundle,
justified for size (psutil, prometheus_client already carried this bar).

## Working rules (carried forward)

- Dormant-by-default: new agent code is imported only by tests, the scan worker, and preflight — never by `main.py` or live request paths.
- SQLModel patterns per AGENTS.md: `session.exec(select(...))`, server-side timestamp defaults, Alembic for schema changes.
- Never commit `.env`, `database/classpilot.db`, `uploads/`, `.opencode/` edits.
- Pre-PR: `pytest tests/ -q` green; frontend build/lint/tsc green if touched.

## Acceptance criteria (v2)

- [x] Failure mode: telemetry job with redaction unwired → clear startup error, NO request sent.
      `mcp.core.jobs.validate_job` and `llms.resolve_for_job` refuse before a
      client is built; `tests/test_llm_routing.py` asserts no request was
      attempted and no outbound row was written.
- [x] Planted email/JWT/phone/IP in DB can never appear in any tool output or LLM request body (asserted on captured requests).
      `tests/test_mcp_core.py` (planted rows through the real registry path),
      `tests/test_mcp_aggregates.py` (per tool), `tests/test_llm_egress.py`
      and `tests/test_llm_routing.py` (captured request bodies).
- [x] Provider outside allowlist → config rejected at startup.
      `Settings.llm_provider` validator; `tests/test_llm_routing.py`.
- [x] `reconcile()` catches a deliberately wrong cited number (test).
      `tests/test_scan_agent_runtime.py` — a wrong number, an unfetched
      metric and a bogus `change_pct` each fail the scan.
- [x] Executor rejects non-enum action; audit row exists for every proposal.
      `tests/test_reactor.py`.
- [x] `docker compose config` shows required networks + internal flag, and the
      monitoring containers are gone from it. `app-internal` is
      `internal: true`, and the preflight asserts the containers and their
      volumes stay gone.
      `app-internal: internal: true`; the monitoring stack is off `edge`.
- [x] `docker run --rm <backend-image> ls .opencode` fails (dev files absent).
      `.dockerignore` excludes `.opencode/`, the Dockerfile asserts it after
      the copies, and the built image was checked.
- [x] `scripts/preflight.py` passes on this repo.
      10 passed, 0 failed, 0 skipped; wired into CI.
- [x] One end-to-end demo scan recorded: subsection filled, audit rows show provider = nvidia_nim, `bytes_out` = redacted payload size.
      `docs/observability/DEMO-SCAN.md` (recorded by `scripts/demo_scan.py`).
- [x] All new + existing tests green; README and SCAN-AGENT.md updated.
      **853 passed / 0 failed** — the first green run in the repository's
      history. The two long-standing failures (the alembic round trip and the
      model/migration drift) are fixed, and the underlying defect they were
      pointing at — a database built from the migration history alone was
      not usable by the app — is fixed too (migrations 021 and 022).
