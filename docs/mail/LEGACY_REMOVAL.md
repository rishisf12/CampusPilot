# LEGACY_REMOVAL.md — everything the old mail implementation leaves behind

This is the clean-slate inventory (Phase 1 of the rebuild). Every path listed
here is removed from the repo in Phase 1. The seven Important subsection
*routes* stay as empty placeholders; everything under `features/mail/`, the
old frontend bundle, the poller and its deploy units, and every mail-related
env var vanish.

The replacements section names where the rebuild supplies the equivalent
capability (Phase 2+). Nothing here is preserved "just in case."

---

## 1. Overview

The old mail system had a simple design: one inbox **per section**, each
section keyed to one receiving mail address (`ug-academics@…`, `registrar@…`
etc.), filed by *which address the mail was sent to*, with a keyword
fallback. It had:
- a SQLModel table `core.mail_message` (+ `core.mail_file`) — 21 columns,
- a FastAPI router `backend/app/features/mail/routes.py`,
- a React bundle `frontend/src/shared/features/mail/` (Mounted from both
  student bundles at the `important` nav tab),
- an IMAP poller script + systemd service/timer,
- env vars `MAIL_MAILBOXES_JSON`, `MAIL_INGEST_SECRET`, `MAIL_FROM`,
  `MAIL_RETENTION_DAYS`,
- tests `backend/app/tests/test_mail.py` (16 tests).

All of it is deleted and replaced by the sender-cluster webmail. No module
outside `features/mail/` references it.

---

## 2. Backend — deleted entirely

### 2.1 `backend/app/features/mail/` (whole directory)

| File | What it did today | Replacement |
|---|---|---|
| `__init__.py` | Package marker only. | New package with the same name, rebuilt in Phases 2–3. |
| `models.py` | `MailMessage`, `MailSenderRule`, `MailFile` (+ `MailDirection`). Route-table model (tables `core.mail_message`, `core.mail_file`). | New models in Phases 1–2: `MailSection`, `MailCluster`, `MailSenderRule`, `MailMessage` (expanded), `MailThread`, `MailLabel`, `MailMessageLabel`, `MailUserMessageState`, `MailAuditLog`, `MailFooterTemplate`, `MailSignature`, `MailUserSettings`. |
| `routes.py` | HTTP surface: `GET /mail/sections`, `GET /mail/messages`, `GET /mail/messages/{id}`, `POST /mail/messages/{id}/read|star`, `POST /mail/compose`, `POST /mail/ingest`, `GET /mail/files`, `GET /mail/messages/{id}/attachments/{file_id}`, `GET/POST/DELETE /mail/sender-rules`. | New router (same paths where they survive the model change: sections/messages/read/star/star/ compose/ingest/files/attachments; `sender-rules` becomes `clusters` + rules). |
| `schemas.py` | Request/response shapes for the old endpoints (`MailMessageResponse`, `MailListResponse`, `MailComposeRequest`, `MailIngestRequest`, `MailFileInfo`, `MailSenderRule…`). | New schemas per endpoint as the model changes. |
| `sections.py` | Section ids/labels (`academics`, `placement`, `cultural`, `technical`, `sports`, `other`) + `classify()` keyword rules. | `sections.py` survives with the ids/labels (the navigation reuses them); `classify()` is demoted to a *suggestion* for the admin — it never files mail anymore. |
| `service.py` | `store_message`, `list_messages`, `mark_read`, `toggle_star`, `store_files`, `list_files`, cluster CRUD (`create_sender_rule`, `match_section_by_sender`), keyword classification. | Rewritten: filing = sender cluster only (exact → domain → pattern → Unassigned); per-account message state (`read`/`starred`/… move from model columns to `core.mail_user_message_state`); user labels; thread grouping; folders/attachment library. |

### 2.2 Migrations — dropped tables

| Migration | Creates | Fate |
|---|---|---|
| `backend/alembic/versions/20261021_0029_mail_messages.py` | `core.mail_message` (21 columns), its indexes. | **Dropped** by `033` (replaced by a new `core.mail_message` with a superset of columns plus new tables). |
| `backend/alembic/versions/20261022_0030_mail_files.py` | `core.mail_file`. | **Dropped** by `033` (replaced by new attachment model with hash/scan status). |
| `backend/alembic/versions/20261022_0031_mail_sender_rules.py` | `core.mail_sender_rule`. | **Dropped** by `033` (replaced by new cluster + rule models). |

These three revisions and their `down_revision` chain are removed from
`backend/alembic/versions/`; the rebuild's Phase 1 migration (`033`) drops
the tables first, then creates the new ones. `test_postgres_migration.py`
verifies models == migrations for every remaining table.

### 2.3 Tests — deleted

| File | What it asserted today |
|---|---|
| `backend/app/tests/test_mail.py` | Ingest auth (401/403), filing by receiving address, keyword fallback, group scoping, read/star, compose/sent copy, reply/forward, sender-rule API (401/403/201/400), re-registration dedupe. |

These are replaced by the Phase 2+ test suites (`test_mail_routing.py`,
`test_mail_clusters.py`, ingestion, UI/e2e). The old `test_mail.py` asserts
the exact behaviour the rebuild removes (filing by receiving address), so it
cannot survive.

---

## 3. Frontend — deleted entirely

### 3.1 `frontend/src/shared/features/mail/` (whole directory)

| File | What it did today |
|---|---|
| `MailInbox.tsx` | The Important-tab mail UI: one inbox per section (`<MailInbox section={…} />`), unread dot + bold sender, subject/snippet, time, star, attachments badge, compose panel, Files panel, Mark unread. |
| `MailCompose.tsx` | Compose/reply/forward panel: To, Subject, Body, Send, quote rendering for forwards. |
| `index.ts` | Exports of both components for the student modules. |

### 3.2 Everywhere the frontend references mail

These files are **edited** (not deleted) to remove their mail dependency:

| File | What is removed |
|---|---|
| `frontend/src/api.ts` | The `mailApi` object: `list`, `compose`, `markRead`, `star`, `download`, `senderRules` (list/create/delete sender rules). |
| `frontend/src/shared/types/api.ts` | The mail block (~30 interfaces): `MailAttachmentMeta`, `MailMessageResponse`, `MailFileInfo`, `MailListParams`, `MailListResponse`, `MailComposeRequest`, `MailSenderRuleInfo`, `MailSenderRuleCreateRequest`. |
| `frontend/src/modules/student-ug/routes.tsx` | The `important` section's sub-nav: `IMPORTANT_TABS`, `importantExpanded`, `importantTab` state, the fourth-row `Tabs`, and `<MailInbox section={importantTab} />` → replaced by `<MailWorkspace />`. |
| `frontend/src/modules/student-pg/routes.tsx` | Same four blocks on the PG bundle. |

### 3.3 What stays untouched

The `Important` nav entry itself and the seven subsection routes
(`academics`, `placement-cell`, `cultural`, `technical`, `sports`, `other`,
`downloads`) stay as empty placeholders ("Mail workspace is being rebuilt")
inside the site's layout — the shell the new workspace mounts into in Phase 2.

---

## 4. Ops — deleted

| File | What it did today | Replacement |
|---|---|---|
| `scripts/ops/imap_mail_poller.py` | IMAP poller: for each group in `MAIL_MAILBOXES_JSON`, reads UNSEEN messages and POSTs them to `/mail/ingest` with the group's secret; marks messages Seen and applies a `Processed/Mail` label. | The new ingestion pipeline (`features/mail/ingestion/`, Phase 4) replaces it — provider-based (`MAIL_PROVIDER=imap|graph|gmail|webhook|dummy`), with dedupe, auth results, thread grouping, and an admin Ingestion log. |
| `deploy/campuspilot-imap-mail-poller.service` | systemd oneshot service that runs the poller every 5 minutes as `www-data` from `/opt/campuspilot/.env`. | Superseded by the provider job (APScheduler) inside the backend process; no separate systemd unit. |
| `deploy/campuspilot-imap-mail-poller.timer` | systemd timer: `OnUnitActiveSec=5min`. | Removed alongside the service. |

---

## 5. Env — deleted

| Var | File | Today's purpose |
|---|---|---|
| `MAIL_MAILBOXES_JSON` | `.env.example` (MAIL APP block) | JSON keyed by group with imap host/user/password, sections→addresses. |
| `MAIL_INGEST_SECRET` | `.env.example` | Fallback ingest secret when a group's JSON block defines none. |
| `MAIL_FROM` | `.env.example` | Envelope sender for outgoing mail. |
| `MAIL_RETENTION_DAYS` | `.env.example` | How long a message is kept. |

These are replaced by the new mail settings block in `.env.example` (`MAIL_PROVIDER`, `MAIL_POLL_INTERVAL_SECONDS`, `MAIL_REQUIRE_AUTH_FOR_ROUTING`, `MAIL_STRIP_PLUS_TAGS`, `MAIL_UNDO_SEND_SECONDS`, `MAIL_RETENTION_DAYS` [retention moves but keeps its name], `MAIL_ATTACHMENT_MAX_BYTES`, `MAIL_QUARANTINE_ENABLED`, `MAIL_INSTITUTE_NAME`, `MAIL_PORTAL_URL`, `MAIL_UNASSIGNED_LABEL`) plus the provider credentials (`MAIL_MAILBOXES_JSON` changes shape — it becomes per-provider config keyed on `MAIL_PROVIDER`).

---

## 6. Deletion checklist

| # | Path | Kind | What it is | Replacement |
|---|---|---|---|---|
| 1 | `backend/app/features/mail/__init__.py` | backend | old package marker | New package (same path, rebuilt) |
| 2 | `backend/app/features/mail/models.py` | backend | MailMessage/MailSenderRule/MailFile models | New models (Phase 1–2) |
| 3 | `backend/app/features/mail/routes.py` | backend | old 13 mail endpoints | New router (Phase 5+) |
| 4 | `backend/app/features/mail/schemas.py` | backend | old request/response shapes | New schemas (Phase 2+) |
| 5 | `backend/app/features/mail/sections.py` | backend | section ids + keyword `classify()` | ids/labels kept; classify → suggestion only |
| 6 | `backend/app/features/mail/service.py` | backend | old filing/compose/file service | Rewritten service (Phase 2–4) |
| 7 | `backend/app/tests/test_mail.py` | test | 16 old mail tests | New test suites (Phase 2–11) |
| 8 | `backend/alembic/versions/20261021_0029_mail_messages.py` | migration | `core.mail_message` | Replaced by `033` |
| 9 | `backend/alembic/versions/20261022_0030_mail_files.py` | migration | `core.mail_file` | Replaced by `033` |
| 10 | `backend/alembic/versions/20261022_0031_mail_sender_rules.py` | migration | `core.mail_sender_rule` | Replaced by `033` |
| 11 | `frontend/src/shared/features/mail/MailInbox.tsx` | frontend | old per-section inbox UI | `MailWorkspace` (Phase 5) |
| 12 | `frontend/src/shared/features/mail/MailCompose.tsx` | frontend | old compose panel | New compose dock (Phase 7) |
| 13 | `frontend/src/shared/features/mail/index.ts` | frontend | old exports | New exports (Phase 2) |
| 14 | `frontend/src/api.ts` | frontend | `mailApi` object | New `mailApi` methods (Phase 5+) |
| 15 | `frontend/src/shared/types/api.ts` | frontend | ~30 mail interfaces | New types (Phase 2+) |
| 16 | `frontend/src/modules/student-ug/routes.tsx` | frontend | UG Important sub-nav + MailInbox mount | Mounts `MailWorkspace` (Phase 2) |
| 17 | `frontend/src/modules/student-pg/routes.tsx` | frontend | PG Important sub-nav + MailInbox mount | Mounts `MailWorkspace` (Phase 2) |
| 18 | `scripts/ops/imap_mail_poller.py` | ops | IMAP poller + `/mail/ingest` POSTs | Provider ingestion pipeline (Phase 4) |
| 19 | `deploy/campuspilot-imap-mail-poller.service` | ops | systemd service (every 5 min) | Removed (APScheduler job inside backend) |
| 20 | `deploy/campuspilot-imap-mail-poller.timer` | ops | systemd timer | Removed |
| 21 | `.env.example` MAIL APP block | env | 4 mail vars | New mail settings block |
| 22 | `docs/MAIL_APP_PLAN.md` | doc | superseded plan | Removed (superseded by docs/mail/*) |

### What must survive
- The `Important` navigation entry and the seven subsection shells
  (`academics`, `placement-cell`, `cultural`, `technical`, `sports`,
  `other`, `downloads`) — they render the empty placeholder until Phase 2,
  then mount `MailWorkspace`.
- Everything outside `features/mail/` and the mail-frontend bundle — the
  schedule, attendance, exam, feedback, teams, OppFeed, monitoring, auth,
  profile modules must keep working exactly as before.

---

## 7. Data worth migrating

The existing development database tables `core.mail_message` and
`core.mail_file` hold ingested mail. Because the rebuild changes the model
(message gets new columns; files get hash/scan status/section), the old rows
are NOT kept verbatim. Migration decision: **start the development database
empty** — the old mail was demo data ingested for testing the old logic, and
the new system seeds its own demo clusters (Phase 1 `seed.py`) and dummy
mail (Phase 4 `seed.py`). No production mail data exists yet, so nothing is
lost.

> The timetable data (`academic.timetable_slot`, etc.) is sacred and is
> never touched by this rebuild.
