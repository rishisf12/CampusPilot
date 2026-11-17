# PostHaven — Implementation Plan

**Project:** PostHaven (multi-user, real-time web mail client)  
**Expands:** Prompt §6 into a concrete per-phase checklist.  
**Versions pinned at plan time** — deviations must be noted with "why".

## Chosen versions / libraries (fixed stack per prompt §2)

| Layer | Choice | Version | Why / notes |
|---|---|---|---|
| Backend framework | FastAPI | 0.115 | Prompt-fixed |
| Backend language | Python | 3.12 (slim) | Prompt-fixed |
| ORM / models | SQLModel | 0.0.23 | Prompt-fixed; SQLAlchemy 2.x |
| Migrations | Alembic | 1.13 | Prompt-fixed |
| Database | PostgreSQL | 16 (alpine) | Prompt-fixed |
| Async DB driver | asyncpg | latest | Prompt-fixed |
| Cache / queue / pub-sub | Redis | 7 (alpine) | Prompt-fixed |
| Background jobs | ARQ | 0.26 | Prompt-fixed (vs Celery — lighter, Redis-native) |
| IMAP client | aioimaplib | latest | Prompt-fixed; IDLE support |
| SMTP client | aiosmtplib | latest | Prompt-fixed |
| MIME parsing | stdlib `email` | — | Prompt-fixed |
| HTML parser/sanitize | selectolax + nh3 | latest | Prompt-fixed |
| Password hashing | passlib[argon2] | latest | Prompt-fixed |
| JWT | python-jose | latest | Prompt-fixed |
| Encryption at rest | cryptography (Fernet/AES-GCM) | latest | Prompt-fixed |
| Settings | pydantic-settings | 2.x | Prompt-fixed |
| Lint / type | ruff + mypy | latest | Prompt-fixed |
| Tests | pytest + pytest-asyncio + httpx | latest | Prompt-fixed |
| Frontend framework | React 18 + TypeScript + Vite | latest | Prompt-fixed |
| CSS | Tailwind CSS v4 | latest | Prompt-fixed (inline via @import) |
| UI primitives | shadcn/ui (Radix) | latest | Prompt-fixed |
| Data fetching | TanStack Query | latest | Prompt-fixed |
| State | Zustand | latest | Prompt-fixed |
| Routing | React Router | latest | Prompt-fixed |
| Virtual list | TanStack Virtual | latest | Prompt-fixed |
| Rich text | TipTap | latest | Prompt-fixed |
| Command palette | cmdk | latest | Prompt-fixed |
| i18n | react-i18next | latest | Prompt-fixed |
| PWA | vite-plugin-pwa | latest | Prompt-fixed |
| Frontend tests | Vitest + React Testing Library | latest | Prompt-fixed |
| E2E | Playwright | latest | Prompt-fixed |
| Mock mail server | greenmail/standalone | latest | Prompt-fixed |
| Frontend server | nginx | alpine | Prompt-fixed |

## Phase checklist (expanded from §6)

### PHASE 0 — Foundation, Docker & Walking Skeleton
- [ ] Repo root: `docker-compose.yml`, `.env.example`, `Makefile`
- [ ] `docs/PLAN.md`, `docs/BUGLOG.md`, `docs/phases/` dir
- [ ] `docker-compose.yml`: `db` (postgres:16), `redis`, `mailserver` (greenmail/standalone), `backend`, `worker`, `frontend` (nginx); healthchecks; `depends_on: condition: service_healthy`; named volumes; `.dockerignore`
- [ ] Backend `Dockerfile` (python:3.12-slim, non-root), `pyproject.toml`, `alembic.ini`, `alembic/env.py`, `alembic/versions/`
- [ ] Backend `app/main.py`: FastAPI, `/health` (+ ready DB+Redis check), `/ready`, structured logging, config via pydantic-settings
- [ ] Backend `app/db/`: async session (asyncpg), SQLModel `Base` metadata
- [ ] Alembic initial migration (empty metadata head) + `upgrade head` / `downgrade base` verified
- [ ] Frontend: Vite + React + TS + Tailwind v4 + shadcn/ui shell, `src/lib/api.ts` typed client, health page calling `/api/v1/health`
- [ ] nginx `nginx.conf`: proxy `/api` + `/ws` to backend; security headers
- [ ] `Makefile`: `up`, `down`, `logs`, `test`, `e2e`, `lint`, `seed`
- [ ] Verification: `docker compose up -d --build` all healthy < 90 s; `/api/v1/health` → `{"status":"ok"}`; `/ready` fails when DB stopped then recovers; Alembic round-trip; frontend loads no console errors; GreenMail reachable `nc -z mailserver 3143`
- [ ] Bug-hunt: start order race, CORS/proxy/WS headers, env typos, port collisions, image caching, `.dockerignore`, secrets in image, non-root, volume persistence
- [ ] Deliverable: `docs/phases/phase-00-report.md`, commit `phase-00: walking skeleton`

### PHASE 1 — Auth, Users & Multi-Tenancy
- [ ] Models: `User`, `RefreshToken`, `UserSetting`, `AuditLog`; migration
- [ ] Endpoints: register, login, refresh (rotation + reuse detection → revoke family), logout, me, change-password; first user = admin
- [ ] Auth deps: `get_current_user`, `get_current_admin`, `owned_or_404` tenant scoping helper
- [ ] Security: argon2, JWT 15-min access + rotating refresh httpOnly cookie, CSRF on cookie flows, rate limit on auth, generic error messages, no password logging/return
- [ ] Frontend: Register/Login pages, route guards, refresh interceptor, session persistence, logout, polished forms with validation
- [ ] Verification: API register→login→me→refresh→logout; refresh reuse revokes family; wrong password ×N rate-limited; expired token rejected; Playwright register → empty inbox shell → reload stays logged in → logout redirects
- [ ] Bug-hunt: case-insensitive dup email, unicode/whitespace emails, SQL-injection strings, overlong inputs, cookie flags, concurrent refresh tabs, clock skew, admin bootstrap race
- [ ] Deliverable: `docs/phases/phase-01-report.md`, commit `phase-01: auth + tenancy`

### PHASE 2 — Mail Accounts, IMAP/SMTP Connectivity & Credential Security
- [ ] Models: `MailAccount`, `Identity`; encryption service (AES-GCM/Fernet from `ENCRYPTION_KEY`)
- [ ] IMAP/SMTP client services: TLS/STARTTLS/plain, timeouts, capability detection (IDLE, CONDSTORE, QRESYNC, SORT/THREAD, MOVE, SPECIAL-USE)
- [ ] Endpoints: provider presets, `POST /accounts/test`, create/list/update/delete account, enable/disable sync
- [ ] SSRF guard + `ALLOW_PRIVATE_MAIL_HOSTS`
- [ ] GreenMail seed script: demo mailboxes via GreenMail API
- [ ] Frontend: Add-account wizard (preset → creds → test → save), accounts list w/ status chips, edit/remove, onboarding empty state
- [ ] Verification: add GreenMail account test pass/fail errors; DB proves ciphertext; API never returns secrets; tenant isolation 404; capability detection stored
- [ ] Bug-hunt: timeouts/leaked sockets, special chars in creds, IDN hosts, SSRF payloads rejected, delete cascades folders/messages/attachments & stops sync
- [ ] Deliverable: `docs/phases/phase-02-report.md`, commit `phase-02: accounts + connectivity`

### PHASE 3 — Mailbox Sync Engine (Folders & Messages)
- [ ] Models: `Folder`, `Message`, `Thread`, `Attachment`; indexes; `search_vector` tsvector trigger; unique `(account_id, folder_id, uid)`
- [ ] Sync service: folder discovery + SPECIAL-USE, initial header sync (latest N), lazy body fetch, backfill job, flag sync, expunge detection, UIDVALIDITY handling
- [ ] MIME parser: html/plain, inline cid images, attachments, charset handling, malformed tolerance, snippet
- [ ] Threading: References/In-Reply-To (JWZ-style) + subject fallback
- [ ] Sanitizer: nh3 allow-list, remote-content classifier, iframe-safe
- [ ] Endpoints: folders CRUD, message list cursor pagination + filters, message/thread detail, attachment stream/download, flag/move/copy/delete (write-through IMAP→DB)
- [ ] Verification: seed GreenMail 500+ varied messages; DB counts match IMAP STATUS; actions round-trip (read/move/delete); p95 list < 150 ms @ 10k msgs; idempotent re-sync; UIDVALIDITY reset handled
- [ ] Bug-hunt: duplicate rows under concurrency (advisory lock), memory on large attachments (stream), XSS corpus neutralized, charset decoding Shift-JIS/ISO-8859/UTF-7, missing Date/Message-ID, N+1 query count assert
- [ ] Deliverable: `docs/phases/phase-03-report.md`, commit `phase-03: sync engine`

### PHASE 4 — Real-Time Engine (IDLE → Redis → WebSocket)
- [ ] Worker supervisor: one resilient IDLE task per enabled account; re-IDLE < 29 min; backoff reconnect; polling fallback; graceful shutdown; Redis lease so exactly one worker owns an account
- [ ] Event bus: worker → Redis channel `user:{id}`; API WS authenticates token, subscribes, forwards; heartbeat 25 s; catch-up `GET /sync/since?cursor=`
- [ ] Frontend: WS client reconnect/backoff, TanStack Query cache patching (insert top, update counts, no full refetch), sync status badge, toast + Web Notification + title count, sound toggle setting
- [ ] Verification: send mail to alice@localhost → Alice tab shows < 2 s no refresh; Bob tab shows nothing; kill worker → restart → catch-up delivers missed mail; kill Redis → recovery; flag change from other IMAP client propagates
- [ ] Bug-hunt: duplicate/out-of-order events, deleted-account events, dual worker lease expiry, zombie IDLE after network drop, WS auth expiry mid-connection, WS leak on logout, cross-tenant channel tampering
- [ ] Deliverable: `docs/phases/phase-04-report.md`, commit `phase-04: real-time engine`

### PHASE 5 — Core Mail UI (Reading Experience)
- [ ] App shell: collapsible sidebar (accounts→folders→labels), virtualized list pane, reading pane, resizable panes, responsive/mobile stack nav
- [ ] Unified inbox + per-account switcher; folder unread badges
- [ ] Message list: skeleton loading, hover actions, multi-select, drag-drop to folders, swipe mobile, density modes
- [ ] Reading pane: header block, sandboxed HTML iframe, remote-images banner, attachment chips + previews (image/PDF/text lightbox), thread collapse/expand, quoted-text folding, view source/headers, print
- [ ] Keyboard shortcuts + `?` cheat sheet + command palette Ctrl/Cmd+K
- [ ] Theme (light/dark/system), density, layout settings; empty/error/offline states
- [ ] Verification: component tests; Playwright open/read/star/archive/delete/undo/drag/keyboard-only; Lighthouse Perf ≥ 85 / A11y ≥ 95; 10k msgs 60 fps virtualized; initial paint < 1.5 s
- [ ] Bug-hunt: iframe height jitter, link safety, dark mode hard-coded colors, focus traps, shortcuts firing while typing, optimistic rollback, stale cache after WS patch, breakpoints 320/768/1440/4K, RTL sample, axe-core pass
- [ ] Deliverable: `docs/phases/phase-05-report.md`, commit `phase-05: reading UI`

### PHASE 6 — Compose, Send & Drafts
- [ ] Compose: TipTap rich + plain mode, To/Cc/Bcc chips + autocomplete, attachments drag-drop + progress + size limits + inline images, identity selector, signature insertion
- [ ] Reply/Reply-all/Forward (inline + as attachment), correct `In-Reply-To`/`References`, `mailto:` handler
- [ ] Drafts autosave (debounce 2 s) → IMAP Drafts + DB; resume; conflict handling
- [ ] Send pipeline via ARQ: undo-send window (5–30 s), send-later (date/time + tz), retry backoff, Sent copy, `send.status` WS events, failed/bounce surfaced
- [ ] Templates with variables, spell check, discard confirmation
- [ ] Verification: E2E Alice→Bob real-time; reply threads both sides; headers asserted via GreenMail; undo → never delivered; send-later T+1 min ±5 s; 20 MB attachment; >limit rejected; draft survives reload/crash
- [ ] Bug-hunt: double-send idempotency, lost attachments reply-all, wrong From, header injection CRLF, RFC 2047/2231 encoding, multipart HTML+text correctness, scheduler drift/DST, job duplication multi-worker, draft/send race, Bcc leak
- [ ] Deliverable: `docs/phases/phase-06-report.md`, commit `phase-06: compose + send`

### PHASE 7 — Search, Labels, Rules, Snooze & Reminders
- [ ] Search service: operator parser (`from: to: cc: subject: has:attachment is:unread|starred|important in: label: before: after: older_than: newer_than: size:`), FTS ranking, highlight, saved/recent searches; UI chips + suggestions
- [ ] Labels: colors, apply/remove/bulk, label filter views
- [ ] Rules engine: conditions × actions (move/label/mark-read/star/delete/forward/auto-reply stop), run on arrival + "run on existing", rule editor UI + test-preview, ordering + stop flag, loop prevention
- [ ] Snooze: picker (later today/tomorrow/next week/custom), worker wake-up → inbox + `snooze.woke`; follow-up reminders; vacation responder (per account, date range, once-per-sender)
- [ ] List-Unsubscribe detection + one-click unsubscribe
- [ ] Verification: 30-query search correctness table on seeded data; p95 < 200 ms @ 50k msgs; rule fires < 2 s on arrival; idempotent run-on-existing; snooze wake after worker restart; reminder only if no reply
- [ ] Bug-hunt: operator edge cases (quotes, negation, unicode), tsquery/SQL injection, rule loops A↔B, auto-reply storms (Auto-Submitted/Precedence: bulk/no-reply@), tz/DST snooze, label deletion consistency, search on unsynced body
- [ ] Deliverable: `docs/phases/phase-07-report.md`, commit `phase-07: search/rules/snooze`

### PHASE 8 — Contacts & Identities
- [ ] Contacts CRUD, groups, auto-collect from sent/received (dedup), merge duplicates, avatar initials (gravatar OFF by default)
- [ ] vCard + CSV import/export w/ validation report
- [ ] Contact profile card (recent threads, last contacted); autocomplete API trigram+prefix < 50 ms
- [ ] Identities: multiple per account, HTML signatures, default per identity, reply-from-matching-identity logic
- [ ] Verification: import 5k-contact vCard; autocomplete latency measured; group send expands; export→import round-trip equality
- [ ] Bug-hunt: vCard 2.1/3.0/4.0 quirks folded lines QP/UTF-8, dup false positives, huge groups, XSS in names/notes
- [ ] Deliverable: `docs/phases/phase-08-report.md`, commit `phase-08: contacts + identities`

### PHASE 9 — Settings, i18n, PWA, Admin & Import/Export
- [ ] Settings: general, appearance, notifications, accounts, identities/signatures, filters, templates, shortcuts, privacy, security (password, sessions + revoke), data export
- [ ] i18n: extract strings; ship `en`, `hi`, `es`, `fr`; language switcher; date/number localization
- [ ] PWA: manifest, service worker (offline shell + cached recent read-only), install prompt
- [ ] Admin: users table (disable/enable/delete), system health (workers, sync lag, queue depth), audit log viewer
- [ ] Import/Export: EML upload, mbox import, export folder as mbox/zip
- [ ] P2 flags: PGP (OpenPGP.js client-side), AI assist panel (provider-pluggable, off unless `AI_PROVIDER`), translation hook
- [ ] Verification: E2E each settings page; language switch no missing keys (scan script); PWA installable Lighthouse; non-admin 403 on admin; import 1k-message mbox
- [ ] Bug-hunt: hard-coded strings, long-language layout, SW stale cache, privilege escalation, session revoke not killing WS, mbox "From " escaping
- [ ] Deliverable: `docs/phases/phase-09-report.md`, commit `phase-09: settings/i18n/PWA/admin`

### PHASE 10 — Hardening: Security, Performance, Resilience
- [ ] Security review: OWASP Top-10 mapped to code; `pip-audit`, `npm audit`, `bandit`, Trivy image scan; dependency pinning
- [ ] Load tests (k6/Locust): 200 concurrent WS users, 50 IDLE accounts, 10 mails/s ingest; record CPU/mem/latency
- [ ] DB: EXPLAIN ANALYZE top 10 queries, missing indexes, pool tuning, vacuum
- [ ] Resilience drills: kill each container, IMAP network partition, Postgres restart, Redis flush — self-heal, no data loss
- [ ] Observability: structured logs + request IDs, `/metrics` Prometheus, dashboard doc
- [ ] Bug-hunt: 1 h soak memory leak, IMAP/DB/WS connection leaks, secret leakage in logs (grep), unbounded queues
- [ ] Deliverable: `docs/phases/phase-10-report.md`, commit `phase-10: hardening`

### PHASE 11 — Full Regression, Documentation & Release
- [ ] Complete Playwright E2E golden paths: register → add account → real-time receive → read/thread → reply → undo send → send later → search → label/rule → snooze → settings/theme/language → admin → logout
- [ ] `README.md` quick start, env vars, architecture diagram, feature matrix ✅/🚧 with source-app inspiration
- [ ] `docs/ARCHITECTURE.md`, `docs/API.md`, `CONTRIBUTING.md`, `docs/OPERATIONS.md` (backup/restore, key rotation, scaling workers, upgrading, real IMAP)
- [ ] `make seed` → demo users + 500 mails/mailbox + live trickle script
- [ ] Fresh-clone test: `git clone` → `cp .env.example .env` → `docker compose up -d --build` → usable
- [ ] Verification: clean-volume suite green; §8 acceptance checklist ticked; all services healthy
- [ ] Bug-hunt: mobile viewport, slow 3G throttling, offline toggle, two devices same user, 30 min tab, no console errors/warnings
- [ ] Deliverable: `docs/phases/phase-11-report.md`, commit `phase-11: release ready`

### PHASE 12 — LAUNCH THE APP
- [ ] `docker compose down -v && docker compose up -d --build`
- [ ] Wait healthchecks; `make seed`; print URLs + demo creds; start `make trickle`; confirm real-time in browser
- [ ] Leave stack running; report status table (service, health, port)

## Exit-gate invariants (every phase)
- Type check clean (mypy backend, `tsc --noEmit` frontend)
- Lint clean (ruff, eslint)
- Tests green for the phase + previous phase smoke suite
- `docs/phases/phase-XX-report.md` written with real evidence
- Commit `phase-XX: <summary>`
- `docker compose up` not broken between phases
