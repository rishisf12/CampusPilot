# CampusPilot

A campus assistant for IIITDM Jabalpur students. One place for the live
timetable, exam schedules and seating, attendance tracking, vacant rooms, and
the notices the college sends by email.

## Stack

| Layer | Tools |
|---|---|
| Backend | Python 3.10+, FastAPI, SQLModel, PostgreSQL, Alembic |
| Frontend | React 18, TypeScript, Vite, Tailwind v4 |
| Auth | JWT bearer tokens, WebAuthn passkeys, email OTP |
| Tests | pytest (backend), vitest/jest (frontend) |
| Deploy | Docker Compose (4 containers), systemd timers for pollers |

## Documentation

- [Quick start](#quick-start)
- [Environment variables](#environment-variables)
- [Deployment](#deployment)
- [Project layout](#project-layout)
- [Features](#features)
- [Mail app](#mail-app)
- [Monitoring](#monitoring)
- [API](#api)
- [Testing](#testing)
- [CSV formats](#csv-formats)
- [Known gaps](#known-gaps)
- [Troubleshooting](#troubleshooting)

Full guides live in [`docs/`](docs): [local development](docs/LOCAL_DEVELOPMENT.md),
[operations runbook](docs/RUNBOOK.md), [adding a feature](docs/ADDING_FEATURES.md),
[security checklist](docs/SECURITY_CHECKLIST.md), [roadmap](docs/ROADMAP.md),
and [architecture notes](docs/architecture). Older planning documents are in
`docs/archive/`.

## Quick start

Requirements: Python 3.10+, Node 18+, PostgreSQL 16. Ports 8000 (backend) and
5173 (frontend) must be free.

### Backend

```bash
cd backend
python -m venv .venv
.venv/Scripts/activate            # Windows; source .venv/bin/activate elsewhere
pip install -r requirements.txt
cp ../.env.example backend/.env   # then fill in SECRET_KEY and SMTP credentials
cd backend
python -m uvicorn main:app --port 8000
```

Migrations run automatically at startup. Check:

```bash
curl http://127.0.0.1:8000/health   # {"status":"ok"}
```

Interactive API docs: <http://127.0.0.1:8000/docs>

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open <http://localhost:5173>. The dev server proxies all backend prefixes to
`http://127.0.0.1:8000` (`VITE_DEV_BACKEND` overrides the target).

Two Windows traps:

- Point the proxy at `127.0.0.1`, not `localhost`. `localhost` resolves to
  `::1` first and uvicorn binds IPv4-only, so every proxied request fails.
- Keep exactly one `vite.config` file. Vite picks `vite.config.js` over
  `vite.config.ts`, so a leftover `.js` silently overrides edits.

### First run

1. Sign up with an `@iiitdmj.ac.in` address and enter the 6-digit code sent to
   it.
2. Upload files through the UI: Live Schedule → Timetable (class timetable),
   Exam → Exam Timetable and Exam Seating Index.
3. Complete Profile (branch, semester, batch year) so exam and attendance
   filters match your registration.

### Admin account

Signup only creates students. Sign up first, then promote:

```bash
python scripts/admin/make_admin.py <college-email>          # from a checkout
docker compose exec backend python scripts/admin/make_admin.py <email>
```

## Environment variables

Backend reads `backend/backend/.env`. Required first; the rest have defaults.

| Variable | Default | Purpose |
|---|---|---|
| `SECRET_KEY` | dev placeholder | JWT signing key, ≥ 32 bytes. Compose refuses to start without it. |
| `DATABASE_URL` | `postgresql+psycopg://campuspilot:campuspilot@localhost:5432/campuspilot` | PostgreSQL only; SQLite is not supported. |
| `ALLOWED_EMAIL_DOMAIN` | `@iiitdmj.ac.in` | Signup domain restriction |
| `SMTP_HOST` / `SMTP_PORT` | `smtp.gmail.com` / `587` | Outgoing mail |
| `SMTP_USER` / `SMTP_PASSWORD` | empty | Mail credentials (Gmail app password) |
| `EMAIL_FROM` | `noreply@iiitdmj.ac.in` | Envelope sender |
| `TIMEZONE` | `Asia/Kolkata` | Clock for schedule and attendance |
| `COLLEGE_START` / `COLLEGE_END` | `09:00` / `17:00` | College hours |
| `ATTENDANCE_SAFE` / `ATTENDANCE_WARNING` | `75` / `65` | Attendance thresholds |
| `MAX_UPLOAD_MB` | `25` | Upload size cap |
| `BRANCH_OPTIONS` | `CSE A,CSE B,DS,ECE,ME,SM,PG,MDes` | Branch list |
| `LLM_PROVIDER` | `off` | `off`, `nvidia_nim` or `openrouter` (see [ADR 0001](docs/ADR-0001-hosted-free-llm.md)) |
| `NVIDIA_API_KEY` / `OPENROUTER_API_KEY` | empty | LLM credentials |
| `TELEMETRY_ENABLED` / `TELEMETRY_PEPPER` | `false` / empty | Telemetry ingest; the API refuses the default pepper |
| `ENABLE_ADMIN_MCP` | `false` | Mounts the admin-only MCP console at `/api/mcp/*` |
| `ENABLE_AGENT` / `ENABLE_SCHEDULER` | `false` | OppFeed agent and its scheduler |
| `FEED_IMAP_HOST` / `FEED_IMAP_USER` / `FEED_IMAP_PASSWORD` | empty | Hackathon feed email ingestion |
| `MAIL_MAILBOXES_JSON` | `{}` | Mail app mailboxes, [see below](#mail-app) |
| `MAIL_INGEST_SECRET` | empty | Fallback ingest secret when a mailbox defines none |
| `MAIL_FROM` | empty | Mail app envelope sender |
| `MAIL_RETENTION_DAYS` | `90` | How long filed messages are kept |

Frontend needs no variables in dev. `VITE_API_URL` only matters when bypassing
the dev proxy.

## Deployment

The compose stack is postgres, adminer, backend, frontend.

```bash
git clone https://github.com/rishisf12/CampusPilot.git && cd CampusPilot
cp .env.example .env
echo "SECRET_KEY=$(python -c 'import secrets; print(secrets.token_urlsafe(48))')" >> .env
docker compose up -d --build
```

Before making a deployment public, set `SECRET_KEY` (never the published dev
one), real `SMTP_*` credentials, a random `TELEMETRY_PEPPER`, `POSTGRES_PASSWORD`
if the database is reachable off-host, and leave `ENABLE_AGENT`/`ENABLE_SCHEDULER`
off until an LLM key is configured. Then verify:

```bash
python scripts/preflight.py    # 11 checks, non-zero exit on any failure
```

The backend runs `alembic upgrade head` on boot; it refuses to start if the
migration would half-apply. The two compose networks separate egress from
everything else: only the frontend and backend containers are on the `edge`
network with a route out.

## Project layout

```
CampusPilot/
├── backend/
│   ├── alembic/            # migrations; versions/ newest last
│   ├── backend/
│   │   ├── main.py         # app entry, router registration
│   │   ├── core/           # config, database, deps, files
│   │   ├── models.py       # SQLModel tables
│   │   ├── features/       # one package per domain (routes + service)
│   │   └── tests/
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── core/           # root router, module selection
│   │   ├── shared/         # auth, components, hooks, types (no feature imports)
│   │   └── modules/        # student-ug, student-pg, admin, faculty (lazy-loaded)
│   └── vite.config.ts      # multi-entry build, dev proxy
├── scripts/                # ops: preflight, admin bootstrap, pollers
├── deploy/                 # systemd service files
├── docs/                   # guides, architecture, archive
└── docker-compose.yml
```

## Features

| Feature | What it does |
|---|---|
| Auth | Signup with college-domain check, email OTP, login, passkeys, password reset |
| Live schedule | Current and next class against the uploaded timetable |
| Attendance | Per-subject tracking, targets, marking with undo, month history |
| Exam | Timetable and seating-index upload, roll-number room lookup |
| Vacant rooms | Room availability for a day and time |
| Feedback | Student feedback with admin replies |
| Teams | Hackathon team creation and skill matching |
| OppFeed | Agent-run internship/job feed with admin moderation |
| Profile | Programme, branch (incl. branch change), electives, attendance target |
| Mail | Per-section inboxes fed from the college's mailboxes (below) |

## Mail app

Every "Important" section (Academics, Placement Cell, Cultural, Technical,
Sports, Other) has its own inbox, fed from the college's mailboxes. Mail is
completely separate from feedback: its own table, endpoints, poller and secret.

- Two programme groups: UG and PG. All six sections of a group share one IMAP
  mailbox; each section has its own receiving address inside it.
- A message is filed under the section whose receiving address it was sent to.
  An address not on the list falls back to keyword classification, which files
  into `other`.
- Students read only their group's mailbox; admins can switch between both.

Configure with a JSON setting:

```
MAIL_MAILBOXES_JSON={"ug":{"imap_host":"imap.gmail.com","imap_port":993,
 "imap_user":"ug@college.ac.in","imap_password":"<app password>",
 "ingest_secret":"<secret>","sections":{"academics":"ug-academics@college.ac.in",
 "placement":"ug-placement@college.ac.in","cultural":"ug-cultural@college.ac.in",
 "technical":"ug-technical@college.ac.in","sports":"ug-sports@college.ac.in",
 "other":"ug-other@college.ac.in"}}}
```

Read by the poller `scripts/ops/imap_mail_poller.py`, which logs in to each
group's mailbox and posts unread messages to `/mail/ingest`; deploy it on the
`campuspilot-imap-mail-poller.timer` from `deploy/`. The poller posts to
`MAIL_INGEST_URL` (default `http://127.0.0.1:8000/mail/ingest`).

Mail endpoints (see `/docs` for schemas): `GET /mail/sections`,
`GET /mail/messages`, `GET/POST /mail/messages/{id}/read|star`,
`POST /mail/compose`, `POST /mail/ingest` (poller only, guarded by the secret).

## Monitoring

Telemetry, dashboards, rollup and alerting live inside the app; there is no
separate metrics stack. Enable with `TELEMETRY_ENABLED=true` and a random
`TELEMETRY_PEPPER` (`/metrics` is served by default). Admin dashboards cover
health, activity, security and feedback per platform. The optional AI scan
reads only a curated set of read-only tools that answer counts and summaries,
and writes every call to `telemetry.tool_call_audit`; a number the audit trail
cannot produce fails the scan. Scans propose remediations only, never execute
them.

Privacy: no IP addresses (truncated HMAC for rate limiting only), no user ids
(HMAC-SHA256 `user_hash` under a server-side pepper), no client-settable
identity, and no free-text props from clients.

## API

Bearer auth on every non-health endpoint. Groups:

| Group | Paths |
|---|---|
| Health | `GET /health` |
| Auth | `/auth/signup`, `/auth/verify-email`, `/auth/login`, `/auth/me`, `/auth/logout`, passkeys |
| Profile | `/profile/`, `/profile/options`, `/profile/branch-change` |
| Schedule & timetable | `/timetable/upload`, `/timetable/slots`, `/schedule/*` |
| Attendance | `/attendance/*` (summary, mark, calendar) |
| Exam | `/exam/*` (timetables, seating, lookup) |
| Rooms | `/rooms/vacant` |
| Feedback | `/feedback/*` |
| Teams | `/teams/*`, `/hackathons/*` |
| Mail | `/mail/*` |
| OppFeed | `/admin/oppfeed/*` (admin), `/faculty/oppfeed*` (read) |
| Monitoring | `/monitoring/*` (admin), `/collect/*` (telemetry ingest), `/metrics` |

Full schemas: <http://127.0.0.1:8000/docs>.

## Testing

Backend tests run against PostgreSQL:

```bash
cd backend/backend
TEST_DATABASE_URL=postgresql+psycopg://campuspilot:campuspilot@localhost:5432/campuspilot_test \
python -m pytest tests/ -q
```

Do not omit `TEST_DATABASE_URL`: the conftest falls back to a scratch SQLite
file, which passes tests the production engine would fail.

Frontend:

```bash
cd frontend
npm run test       # vitest
npx tsc --noEmit   # type check
npm run lint
npm run build
```

Before every PR: backend suite green, frontend build/lint/typecheck green,
`python scripts/preflight.py` from `CampusPilot/`.

## CSV formats

Class timetable (all seven columns required; malformed rows warn, not fail):

```csv
day,start_time,end_time,room,course_code,branch_or_program,semester
Mon,09:00,10:00,L-101,CS5031,BTech CSE,5
```

Seating index (rolls `YYBBBNNN`; ranges compared numerically within a prefix):

```csv
roll_range,room,date,time,course_code
23BCS001-23BCS050,L-101,2026-09-21,08:00-10:00,CS8036
```

Mid-sem exam timetable (empty branch = all branches of the semester):

```csv
date,time,course_code,semester,branch
2025-09-29,10:30AM-12:30PM,CS8036,7,CSE
```

## Known gaps

- The attendance target is stored in the browser (`localStorage`), not the
  server.
- Exam timetable rows carry no instructor field; that column shows `—`.
- A paper's hall is inferred from the seating index; a paper the index does not
  cover has no exact hall.
- Verification codes are in-memory: lost on restart, not shared across workers.
- Timetable and exam uploads are global, one cohort; multi-branch uploads need
  a scope key.

## Troubleshooting

| Symptom | Fix |
|---|---|
| "Backend offline" in the header | Backend not on port 8000; `curl http://127.0.0.1:8000/health` |
| Signup rejected | Email must end with `@iiitdmj.ac.in`; username and roll must be unique |
| No verification email | Check `SMTP_USER`/`SMTP_PASSWORD`; Gmail needs an app password; use Resend after 60 s |
| Upload finds no rows | File has no text layer (scanned image) or is a 0-byte download |
| Live Schedule empty | No class timetable uploaded yet |
| Attendance has no subjects | They sync from the timetable; upload it, then refresh |
| 401 on every dev request | Vite proxy shadowed by a stale `vite.config.js`, or pointing at the wrong port |
| Windows: all proxied requests 500 | Proxy target must be `127.0.0.1`, not `localhost` |

## License

MIT.
