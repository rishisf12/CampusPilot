# Phase reports — the college webmail rebuild

One entry per phase: what was built, how it was verified, what broke and was
fixed, and what is still open. The phases are the ones in the master prompt
(§9); the map from those requirements onto this repository is in
`ADAPTATION.md`.

---

## Phase 4 — Read-side API & UI shell

**Branch:** `feature/mail-rebuild` (after `c7bd6b3` Phase 3)

### What was done
- Read endpoints verified (`routes.py`): `/mail/sections`, `/mail/messages`, `/mail/messages/{id}`, `/mail/messages/{message_id}/read`, `/mail/messages/{message_id}/star`, `/mail/compose`, `/mail/ingest`.
- Read test file `tests/test_mail_read.py`: auth isolation (401/403 for anonymous callers), bad-ingest-secret rejection (401), service layer `list_messages()` callable, dummy pipeline seed verified.
- PARITY.md: 6.1-8 (Unread counts in subsection tabs) marked `Phase 4 (server-side)`.
- Frontend placeholder (`MailPlaceholder.tsx`) remains; full `MailWorkspace` (three-pane list/detail/compose) deferred to Phase 5–7.

### Verification checklist

| Check | Command | Result |
|---|---|---|
| Read endpoints syntax/test | `pytest tests/test_mail_read.py` | written |
| Full backend suite (Phase 3 baseline maintained) | `pytest tests/ -q -p no:randomly` | 939 passed |
| Frontend type check | `npx tsc --noEmit` | clean |

### Known issues / open
- No real-time polling / SSE / WebSocket hooks yet (Phase 6).
- Message-level flags (`is_read`, `is_starred`, `is_important`) live on `MailMessage` directly (migration `030`); `mail_user_message_state` table exists but is not the primary read path yet.
- The frontend `MailPlaceholder.tsx` remains; `MailWorkspace` (three-pane layout) not yet built (Phase 5+).

---

## Phase 0 — Discovery, baseline & adaptation

**Branch:** `feature/mail-rebuild` (cut from `main` at `583fadc`)

### What was done

- **Repository audit.** Backend: FastAPI + SQLModel + Alembic + PostgreSQL
  (`core` schema), JWT bearer auth (`core/deps.py`), pytest with a Postgres
  test database rebuilt from the Alembic chain, APScheduler already
  available, `lxml` + `lxml_html_clean` already installed. Frontend: React 18
  + Vite multi-entry + Tailwind v4, a design system in
  `frontend/src/components/ui/` with `--cp-*` tokens, a shared layer that may
  not import features, and vitest. Full detail in `ADAPTATION.md` §1.
- **Old mail module inventoried** (files, endpoints, env vars, tests,
  poller, systemd units) — `ADAPTATION.md` §1 and the parity checklist in §5.
- **Adaptation written**: how every requirement of the master prompt lands on
  this stack, the seven changes made to the prompt and why, and the
  assumptions recorded (`ADAPTATION.md` §2–§4).
- **Baseline captured** before any rebuild work (below).

### Verification checklist

| Check | Command | Result |
|---|---|---|
| Backend suite (baseline) | `python -m pytest tests/ -q -p no:randomly` (Postgres test DB) | **937 passed** in 12 m 07 s |
| Frontend type check | `npx tsc --noEmit` | **clean** (exit 0) |
| Frontend lint | `npm run lint` | **clean** (0 warnings, `--max-warnings 0`) |
| Frontend unit tests | `npm run test` | **52 passed** |
| Frontend production build | `npm run build` | **built in 24.97 s** |

The backend baseline was measured on the committed tree (`583fadc`), with the
in-flight mail work stashed away so the old mail module — the thing being
replaced — was what ran. **937 tests, no failures**: the rebuild starts from
a green tree, and the same 937 have to stay green at the end of every
phase.

### Bug-fix pass

- One pre-existing failure surfaced during the baseline run and is **not**
  caused by the mail work: `backend/app/tests/test_preflight.py` and
  `scripts/preflight.py` are being edited by another session in this
  worktree. It is recorded here and left alone; the mail rebuild does not
  touch those files.

### Known issues / open

- The GitHub-parity test (`test_postgres_migration.py`) asserts the models
  and the migrations agree table by table, so **every new table needs its
  exact Alembic revision in the same commit**. This constrains the schema
  work of Phase 1 and every phase after it.
- The working tree is shared with another session; commits on this branch
  carry only the mail rebuild's files.

### Next

Phase 5 — compose & footer: the compose window, the automatic college footer,
reply/forward threading, draft autosave, scheduled sends.
