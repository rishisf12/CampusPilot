# ADAPTATION.md — the college webmail rebuild, mapped onto this repository

This is Phase 0 of the mail rebuild: what the repository already is, how the
master prompt's requirements land on it, what I changed in the prompt and
why, and the checklist the new system has to satisfy before the old one is
removed.

---

## 1. The stack this project actually has

### Backend

| Concern | What is here | Notes for the mail rebuild |
|---|---|---|
| Framework | **FastAPI** (`backend/app/main.py`), routers per feature | The mail feature is one router: `backend/app/features/mail/routes.py` |
| ORM | **SQLModel** (SQLAlchemy 2.x) on **PostgreSQL** (`core` schema) | New tables go in the `core` schema, like every other feature |
| Migrations | **Alembic** (`backend/alembic/versions/`), numbered revisions | A revision is a plain `op.create_table` script, Postgres-guarded |
| Auth | **JWT bearer** (`core/deps.py`: `get_current_user`, `get_current_admin`), `UserRole` = `student` / `admin` | The prompt's four roles map onto this (see §3) |
| Tests | **pytest**, `backend/app/tests/`, Postgres test DB rebuilt from the Alembic chain by `conftest.py` | `test_postgres_migration.py` asserts the models and the migrations agree, table by table — every new table must ship with an exact migration |
| Scheduling | **APScheduler** is already a dependency (the OppFeed daily agent job) | The prompt's background worker maps to APScheduler, not a new queue |
| HTML handling | `lxml` + `lxml_html_clean` are **already dependencies** | Server-side sanitisation uses `lxml_html_clean` — no new package |
| Config | `core/config.py` (`Settings`, pydantic-settings), `.env` at the repository root | New settings are `MAIL_*` fields there |

### Frontend

| Concern | What is here | Notes for the mail rebuild |
|---|---|---|
| Framework | **React 18 + TypeScript + Vite** (multi-entry build: main + four lazy modules) | The mail UI lives in `frontend/src/shared/features/mail/` |
| Styling | **Tailwind CSS v4** (through PostCSS) with a **design system** in `frontend/src/components/ui/` (`Button`, `Card`, `Badge`, `Input`, `Textarea`, `Select`, `Tabs`, `Table`, `Modal`, `Toggle`, `ProgressBar`, `IconTile`) and CSS tokens `--cp-*` in `src/index.css` | The mail UI uses these components and tokens; it must look native to the site |
| API layer | `frontend/src/api.ts` (a `request` helper + one object per domain) and `frontend/src/shared/types/api.ts` | New endpoints extend `mailApi` and the shared types |
| Architecture rule | `src/shared/` may not import from `src/features/`; modules import from `@shared/*` | The mail bundle stays inside `src/shared/features/mail/` so both student bundles can mount it |
| Routing | `src/core/App.tsx` picks a module by role; `student-ug` and `student-pg` each render their own "Important" navigation | The new mail app is mounted in both student modules, one instance each |
| Tests | **vitest** (`src/tests/*.test.ts`), `npm run test` | Pure logic (query parsing, keyboard map, counts) goes here |

### The old mail module (what Phase 10 removes)

```
backend/app/features/mail/{__init__,models,routes,schemas,sections,service}.py
backend/app/tests/test_mail.py
backend/alembic/versions/20261021_0029_mail_messages.py
backend/alembic/versions/20261022_0030_mail_files.py
frontend/src/shared/features/mail/{MailInbox.tsx,MailCompose.tsx,index.ts}
scripts/ops/imap_mail_poller.py          + deploy/campuspilot-imap-mail-poller.{service,timer}
```

Old endpoints: `GET /mail/sections`, `GET /mail/messages`, `GET /mail/messages/{id}`,
`POST /mail/messages/{id}/read|star`, `POST /mail/compose`, `POST /mail/ingest`,
`GET /mail/files`, `GET /mail/messages/{id}/attachments/{file_id}`.

Old env: `MAIL_MAILBOXES_JSON`, `MAIL_INGEST_SECRET`, `MAIL_FROM`,
`MAIL_RETENTION_DAYS`.

Old behaviour: one inbox **per section**, filed by the **receiving address**
(the address a notice was sent to), with a keyword fallback. That is exactly
what the rebuild replaces.

---

## 2. Where each requirement of the prompt lands

| Prompt | In this project | Phase |
|---|---|---|
| §2.1 sender clusters | `core.mail_cluster` + `core.mail_sender_rule` (type, value, section, priority, active, notes, created_by/at) | 1, 2 |
| §2.2 `routeMail(message)` | `features/mail/routing/route.py` — a pure function over a parsed message | 2 |
| §2.2 unassigned queue, retro-apply, re-route, audit | `core.mail_routing_audit` + admin endpoints | 2 |
| §2.3 routing unit tests (table-driven) | `backend/app/tests/test_mail_routing.py` | 2 |
| §2.4 SPF/DKIM/DMARC | `core.mail_message.auth_*` columns, `ingestion/auth.py`, admin Quarantine view | 3 |
| §3 provider adapters | `features/mail/providers/{base,dummy,imap}.py` + `factory.py` keyed on `MAIL_PROVIDER` | 3 |
| §3 dummy seeds, dev tools | `features/mail/seed.py`, admin "Dev Tools" screen | 3 |
| §3 ingestion pipeline | `features/mail/ingestion/pipeline.py`: receive → parse → authenticate → dedupe → route → thread → store → index → notify | 3 |
| §4 data model | the entity list in §4 of the prompt, as SQLModel tables in the `core` schema with an Alembic revision each phase | 1 (core), 4–8 (the rest) |
| §5 roles | `UserRole` gains `section_admin`; `core.mail_section_access` says which sections an account may read/manage | 1 |
| §6.1 three-pane layout, sidebar | `frontend/src/shared/features/mail/` — `MailLayout`, `MailSidebar`, `MailList`, `ReadingPane` | 4 |
| §6.2 message list, bulk actions | `MailList` + `mailApi.bulk` | 4 |
| §6.3 reading pane, safe HTML, routing reason | `ReadingPane`; server-sanitised HTML via `lxml_html_clean` | 4 |
| §6.4 compose | `MailCompose` (already exists in the old module — reworked, not rewritten from nothing) | 5 |
| §6.5 automatic college footer | `features/mail/compose/footer.py` + `core.mail_footer_template` | 5 |
| §6.6 search operators, saved searches, filters | `features/mail/search/query.py` + `core.mail_saved_search`, `core.mail_user_filter` | 6 |
| §6.7 Downloads library | `features/mail/downloads/` + `core.mail_attachment`; replaces the old Files panel | 7 |
| §6.8 notifications | `core.mail_notification` + SSE endpoint + bell | 6 |
| §6.9 settings & admin console | `frontend/src/modules/admin/features/mail/` + `core.mail_user_settings` | 8 |
| §7 security | sanitisation, CSP headers, rate limits, validation, audit | 9 |
| §8 directory structure | `backend/app/features/mail/{routes,services,providers,ingestion,seeds}`; the prompt's `src/modules/mail` becomes one feature package | 1–8 |
| §9 phases | this document's phases, one commit each, reports in `docs/mail/PHASE_REPORTS.md` | 0–11 |
| §10 acceptance criteria | checked in Phase 11, one test per criterion | 11 |
| §11 deliverables | `docs/mail/{ADAPTATION,PHASE_REPORTS,ARCHITECTURE,ROUTING,PROVIDERS,MIGRATION,USER_GUIDE}.md` | 11 |

---

## 3. Changes made to the prompt, and why

1. **Language and framework.** The prompt's directory layout is
   TypeScript-shaped (`src/modules/mail`, `controllers/`, `.ts` services). The
   project is Python/FastAPI/SQLModel on the backend and React/TypeScript on
   the frontend, so the backend keeps the project's own feature-package
   shape: `backend/app/features/mail/` with `routes.py`, `service.py`,
   `models.py`, `schemas.py` plus the new `routing/`, `ingestion/`,
   `providers/`, `compose/`, `search/`, `downloads/` sub-packages. The
   prompt's *structure* is kept; only the language changes.
2. **Sanitisation without a new dependency.** The prompt names DOMPurify.
   The project has no DOMPurify and adding an npm package for one feature is
   avoidable: `lxml_html_clean` is already a backend dependency, so HTML is
   sanitised **server-side** (allow-list) and the client renders only what
   the server vouches for. No frontend dependency is added.
3. **Roles.** The project has `student` and `admin`. The prompt's
   *Super Admin* is `admin`; *Section Admin / Moderator* becomes a per
   section permission (`core.mail_section_access`) rather than a second
   global role enum, because the same person may moderate one section and
   read another; *Member* and *Student/Viewer* are both `student`, with
   section visibility enforced server-side.
4. **`MAIL_PROVIDER`.** `dummy` and `imap` are implemented for real; `graph`,
   `gmail` and `webhook` ship as documented interfaces with an explicit
   "not implemented yet" error, so the factory is honest about what
   exists. A real provider is then configuration only.
5. **The six aliases are one group's intake.** The prompt lists the UG
   aliases. The project has two mail groups (UG and PG), so the PG group
   gets its own six aliases, configured the same way.
6. **Migrations are per phase.** The project enforces model/migration parity
   with a test, so each phase that changes the schema ships its Alembic
   revision in the same commit, and the revision creates exactly what the
   models declare.
7. **Commit scope.** The repository is worked on by more than one session.
   Commits on this branch carry only the mail rebuild's files; another
   session's files (`core/config.py`, `main.py`, `monitoring/`, `mcp/`,
   `scripts/preflight.py`) are left out of these commits.

---

## 4. Assumptions

1. `registrar@iiitdmj.ac.in` is the Academics-related address — but the
   address never decides a section. It is recorded as the intake address and
   shown in the UI.
2. The six addresses are **aliases of one intake**: a notice sent to any of
   them enters the same mailbox and is filed by its sender.
3. A sender nobody registered goes to **Unassigned** — visible to admins,
   invisible to students as a section (it is a queue, not a folder). One
   click puts the sender in a cluster, optionally re-filing the mail it
   already wrote.
4. Authentication results (SPF/DKIM/DMARC) are parsed when the provider
   supplies them; in dummy mode the provider simulates them. The setting
   `REQUIRE_AUTH_FOR_ROUTING` defaults **off** in dummy mode and **on** when
   a real provider is configured.
5. "Downloads" is the attachment library, not a sender-routed inbox.
6. The old per-section inboxes and the per-section sub-navigation are
   removed in Phase 10, once the new system has parity. The sender-cluster
   work that already exists is the seed of the new routing engine, not
   something to be thrown away.

---

## 5. Feature-parity checklist (old mail → new mail)

| # | Old capability | Where it lands in the new system | Status |
|---|---|---|---|
| 1 | Ingest guarded by a group secret | `POST /mail/ingest` (secret) + the provider pipeline | kept, extended |
| 2 | One mailbox per group (UG / PG) | Group scoping on every read; the six aliases are one intake | kept, extended |
| 3 | Section folders with counts | Sidebar folders (Academics … Other, Downloads) with unread counts | replaced |
| 4 | Filing by receiving address | **Filing by the sender's cluster** (exact → domain → pattern → Unassigned) | replaced |
| 5 | Keyword fallback | Admin *suggestion* only; never files | replaced |
| 6 | Search over sender/subject/body | Search service with operators, saved searches, highlights | extended |
| 7 | Star / mark read / mark unread | `UserMessageState` per user, bulk actions | extended |
| 8 | Compose, reply, forward | Compose window, reply all, drafts, undo/schedule send, footer | extended |
| 9 | Attachments (bytes stored, download) | `core.mail_attachment` with hash, scan status, preview, ZIP | extended |
| 10 | Files (downloads) panel | Downloads library (§6.7) | replaced |
| 11 | Group isolation (a student sees only their group's mail) | Server-side, per section and per group | kept, strengthened |
| 12 | IMAP poller (`scripts/ops/imap_mail_poller.py`) | `providers/imap.py` behind `MAIL_PROVIDER=imap` | replaced |
| 13 | Section ids shared with the "Important" navigation | `core.mail_section`, seeded from the same ids | kept |
| 14 | Retention setting (`MAIL_RETENTION_DAYS`) | Retention job over trash and archive | kept |
| 15 | Mail tests (`test_mail.py`, 16 tests) | Rewritten as the routing/ingestion/UI suites | replaced |
