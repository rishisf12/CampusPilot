# Essential — Your Campus Assistant

A campus assistant for IIITDM Jabalpur students. Upload the class timetable, the
mid-sem exam timetable and the exam seating index once, and the app answers the
three questions that matter every semester:

- **What class do I have right now?** Live schedule from the system clock.
- **Where is my exam, and when?** Roll-number lookup with rooms and halls.
- **Am I safe on attendance?** Per-subject tracking against your target.

Backend: FastAPI + SQLModel + PostgreSQL 16. Frontend: React 18 + Vite.

---

## Table of contents

- [Quick start](#quick-start)
- [Environment variables](#environment-variables)
- [Project layout](#project-layout)
- [Features](#features)
- [Monitoring](#monitoring)
- [API reference](#api-reference)
- [Data model](#data-model)
- [How the exam system works](#how-the-exam-system-works)
- [How the frontend maps to the backend](#how-the-frontend-maps-to-the-backend)
- [Testing](#testing)
- [CSV templates](#csv-templates)
- [Known gaps](#known-gaps)
- [Troubleshooting](#troubleshooting)

---

## Quick start

### Prerequisites

| Requirement | Version |
|---|---|
| Python | 3.10+ (developed and tested on 3.10.10) |
| Node.js | 18+ (tested on 24.14) |
| Free ports | **8000** (backend), **5173** (frontend) |

### 1. Backend

```bash
git clone https://github.com/rishisf12/CampusPilot.git
cd CampusPilot

cd backend
python -m venv .venv
.venv/Scripts/activate        # Windows
# source .venv/bin/activate   # macOS / Linux

pip install -r requirements.txt
```

Copy the environment template and fill in your secrets:

```bash
cp .env.example backend/backend/.env    # macOS / Linux / Git Bash
copy .env.example backend\backend\.env  # Windows cmd
```

`SECRET_KEY` and the SMTP values are required for login and email verification —
see [Environment variables](#environment-variables).

Start the API:

```bash
cd backend/backend
python -m uvicorn main:app --port 8000
```

PostgreSQL is the only supported database. Point `DATABASE_URL` at your server
(see [Environment variables](#environment-variables)); Alembic migrations run
automatically at startup, so a fresh database is created and brought to head
without a separate step. Check it is alive:

```bash
curl http://127.0.0.1:8000/health     # {"status":"ok"}
```

Interactive API docs: <http://127.0.0.1:8000/docs>

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

Open <http://localhost:5173>. The Vite dev server proxies every backend prefix
(`/auth`, `/profile`, `/schedule`, `/timetable`, `/rooms`, `/attendance`,
`/exam`, `/health`, `/ocr`, `/feedback`, `/teams`, `/hackathons`,
`/monitoring`, `/collect`, `/metrics`) to `http://127.0.0.1:8000`, so the app
runs same-origin and needs no CORS setup.

Set `VITE_DEV_BACKEND` to point the proxy somewhere else, e.g.
`http://127.0.0.1:8002` when the backend runs in Docker. Use the IP literal
rather than `localhost`: on Windows `localhost` resolves to `::1` first and
uvicorn binds IPv4-only, which makes every proxied request fail with a 500 and
an empty body.

There must be exactly **one** `vite.config` file. Vite resolves
`vite.config.js` before `vite.config.ts`, so a leftover `.js` silently wins and
the `.ts` you are editing has no effect.

### 3. First run

1. **Sign up** with your `@iiitdmj.ac.in` address — other domains are rejected.
2. Enter the 6-digit code from your inbox. If you close the tab mid-flow, reopen
   it: the pending address is remembered and you land back on the code screen.
3. Upload data from the UI:
   - **Live Schedule → Timetable** → class timetable (PDF or CSV)
   - **Exam** → *Exam Timetable* and *Exam Seating Index*
4. Set **Profile → Branch / Semester / electives** so the exam and attendance
   filters line up with your registration.

---

## Environment variables

Backend reads `backend/backend/.env` (see `.env.example`).

| Variable | Default | Purpose |
|---|---|---|
| `SECRET_KEY` | dev placeholder | JWT signing key. **Must be ≥ 32 bytes for HS256.** Set your own. |
| `ALGORITHM` | `HS256` | JWT algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `10080` (7 days) | Token lifetime |
| `DATABASE_URL` | `postgresql+psycopg://campuspilot:campuspilot@localhost:5432/campuspilot` | Database. Must be `postgresql+psycopg` — only this dialect is supported.
SQLite is not part of the project. Do not set `TEST_DATABASE_URL`; the conftest
defaults to a scratch SQLite file, which is incompatible with the production
engine and will silently pass tests that would fail on PostgreSQL. Always run
pytest against PostgreSQL: ``TEST_DATABASE_URL=postgresql+psycopg://... python -m pytest``.
| `DB_POOL_SIZE` / `DB_MAX_OVERFLOW` | `10` / `10` | Connection pool for PostgreSQL. Only applies when `TEST_DATABASE_URL` points at Postgres.
| `DB_POOL_RECYCLE` | `1800` | Recycle a pooled connection after N seconds, before a NAT/firewall can drop it. |
| `DB_SSLMODE` | `prefer` | TLS to the database. Use `require` off-host. |
| `ALLOWED_EMAIL_DOMAIN` | `@iiitdmj.ac.in` | Only this domain may register |
| `SMTP_HOST` / `SMTP_PORT` | `smtp.gmail.com` / `587` | Outgoing mail |
| `SMTP_USER` / `SMTP_PASSWORD` | empty | Mail credentials (Gmail needs an app password) |
| `EMAIL_FROM` | `noreply@iiitdmj.ac.in` | Envelope sender |
| `FRONTEND_URL` | `http://localhost:5173` | CORS origin |
| `TIMEZONE` | `Asia/Kolkata` | Server clock for schedule/attendance |
| `COLLEGE_START` / `COLLEGE_END` | `09:00` / `17:00` | College hours |
| `LUNCH_START` / `LUNCH_END` | `13:00` / `14:00` | Lunch window |
| `ATTENDANCE_SAFE` / `ATTENDANCE_WARNING` | `75` / `65` | Status thresholds |
| `MAX_UPLOAD_MB` | `25` | Upload size cap |
| `ALLOWED_EXTENSIONS` | `.pdf,.csv` | Accepted upload types |
| `BRANCH_OPTIONS` | `CSE A,CSE B,DS,ECE,ME,SM,PG,MDes` | Canonical branch list |
| `ADMISSION_YEAR` | `21` | Anchor for roll → semester inference |

The frontend has no required variables. Set `VITE_API_URL` only if you want to
bypass the dev proxy and call the API directly.

---

## Project layout

```
CampusPilot/
├── .env.example                  # Backend environment template
├── INTEGRATION_CHECKLIST.md
├── database/
│   └── classpilot.db             # Legacy SQLite file — kept only for the one-shot migration
├── backend/
│   ├── requirements.txt
│   ├── alembic.ini               # Migrations. No sqlalchemy.url: it carries a password
│   ├── alembic/
│   │   ├── env.py                # Wired to SQLModel.metadata + the app's own engine
│   │   └── versions/             # Revision history, newest last
│   └── backend/
│       ├── main.py               # App, CORS, lifespan, router registration
│       ├── core/                 # Shared infrastructure
│       │   ├── config.py         # Settings + derived constants
│       │   ├── database.py       # Engine, session, schema creation & migration
│       │   ├── deps.py           # FastAPI dependencies (auth, session)
│       │   └── files.py          # Upload validation & storage
│       ├── models.py             # SQLModel tables
│       ├── features/             # Feature packages (routes + service)
│       │   ├── attendance/       # Attendance tracking
│       │   ├── auth/             # Login, signup, passkeys, password reset
│       │   ├── exam/             # Exam timetable, seating, clash, PDF
│       │   ├── feedback/         # Student feedback + admin replies
│       │   ├── profile/          # Programme, semester, branch, electives
│       │   ├── rooms/            # Vacant room lookup
│       │   ├── monitoring/       # Telemetry ingest, metrics, admin monitoring, AI scans
│       │   │   ├── api/         # routes.py (/monitoring/*, /collect/*), schemas.py
│       │   │   ├── domain/      # models.py (monitoring tables), thresholds.py
│       │   │   ├── infrastructure/  # collector, rollup, metrics, ratelimit
│       │   │   └── services/    # queries, scan_service, feedback_analysis, llm_client
│       │   ├── schedule/         # Live schedule (current/next class)
│       │   ├── teams/            # Hackathon teams & matching
│       │   └── timetable/        # Class timetable upload & parsing
│       ├── ocr/                  # Optional OCR extraction
│       ├── scripts/seed.py       # Demo data
│       ├── tests/                # 790 tests (PostgreSQL)
│       └── uploads/              # Runtime uploads (git-ignored)
├── frontend/
│   ├── index.html                # Title, favicon, Tailwind palette, CSS reset
│   ├── vite.config.ts            # Port 5173, proxy → 127.0.0.1:8000
│   ├── nginx.conf                # Container proxy; uses try_files, no per-router list
│   ├── tsconfig.json
│   ├── public/
│   │   ├── logo.svg              # Lightbulb lockup + wordmark
│   │   └── logo-icon.svg         # Icon: 9/11/2 rings, smile, teal
│   └── src/                      # TypeScript (.tsx) — the .jsx migration is complete
│       ├── main.tsx
│       ├── App.tsx               # Single header, nav, footer
│       ├── api.ts                # fetch wrapper + all endpoints
│       ├── constants.ts          # Branches, programmes, semesters
│       ├── telemetry.ts          # /collect/events batched sender
│       ├── index.css             # Component classes
│       ├── types/api.ts          # Shared API response types
│       ├── components/           # Shared UI components
│       │   ├── AuthWrapper.tsx   # Session context, /auth/me retry
│       │   ├── LoginForm.tsx
│       │   ├── SignupForm.tsx
│       │   ├── VerifyEmail.tsx   # 6-digit OTP + resend cooldown
│       │   ├── FileUpload.tsx
│       │   ├── ErrorBanner.tsx
│       │   ├── Spinner.tsx
│       │   ├── StatusCard.tsx
│       │   ├── StartScreen.tsx
│       │   ├── SignupEmail.tsx
│       │   ├── PasswordReset.tsx
│       │   ├── PasskeyPrompt.tsx
│       │   ├── PasskeyRecovery.tsx
│       │   ├── ManagePasskeys.tsx
│       │   ├── NavIcons.tsx
│       │   └── UploadPreview.tsx
│       ├── features/             # Feature-specific UI
│       │   ├── admin/            # AdminPanel
│       │   ├── classroom/        # Attendance, ExamSeating, LiveSchedule, VacantRoomLookup
│       │   ├── feedback/         # Feedback form + history
│       │   ├── profile/          # Profile page
│       │   ├── monitoring/       # Admin monitoring dashboard
│       │   │   ├── Monitoring.tsx        # Section shell, subsection nav, freshness badge
│       │   │   ├── panels/Health.tsx     # A: Health & Performance
│       │   │   ├── panels/Activity.tsx   # B: User Activity
│       │   │   ├── panels/Security.tsx   # C: Security
│       │   │   ├── panels/Feedback.tsx   # D: Feedback
│       │   │   ├── panels/Monetisation.tsx
│       │   │   ├── panels/History.tsx    # Scan history + incident log
│       │   │   └── components/components.tsx  # StatTile, Panel, StatusPill, ...
│       │   └── myteam/           # Teams, Hackathons, CreateTeam, MatchScore
│       ├── hooks/                # React hooks
│       │   ├── useLiveDay.ts
│       │   ├── useProfile.tsx
│       │   ├── useProfileCourses.ts
│       │   └── useProfileVersion.ts
│       ├── lib/                  # Utilities
│       │   ├── normalise.ts
│       │   ├── passkey.ts
│       │   ├── storage.ts
│       │   ├── sync.ts
│       │   └── time.ts
│       └── tests/
│           └── passkey.test.js
├── mcp-crash-monitor/            # Read-only MCP server over the monitoring tables
│   └── src/index.ts
├── ops/
│   └── prometheus/               # Prometheus config, alert rules, blackbox modules
└── tools/                        # Maintenance scripts (not part of the app)
```

---

## Features

### Authentication

- JWT bearer tokens, HS256, 7-day expiry, `sha256_crypt` password hashing.
- Login is an OAuth2 password form (`application/x-www-form-urlencoded`).
- Signup enforces `@iiitdmj.ac.in` on the server **and** in the form.
- Email verification: 6-digit code, 10-minute expiry, resend with cooldown.
- Every protected route requires `Authorization: Bearer <token>`.
- On reload the session is re-validated with `/auth/me`, retried twice so a
  backend that is still booting does not sign the user out. **Only a genuine 401
  clears the session** — network errors keep you signed in and show "offline".

### Profile

- Programme, semester (options follow the programme), branch, electives.
- Branches are exactly `CSE A, CSE B, DS, ECE, ME, SM, PG, MDes` — no bare
  `CSE`, no duplicates. `DS` is the BDes branch.
- Elective and extra/backlog courses added by course code. `OE…` codes are open
  to every branch and are stored as electives; anything else becomes an extra
  course.
- Attendance target percentage.
- **Branch change** lives inside the Profile card: From / To dropdowns (both
  placeholder "Select branch"), a *Change Branch* button, and a *"No branch
  change"* checkbox beside it. Ticking the box clears any pending request;
  making a change unticks it automatically. `original_branch` is preserved
  across every subsequent change.
- Any profile or branch change bumps `localStorage['profile_version']` and fires
  a `profile-updated` event, which makes the Exam tab refetch.

### Live schedule

- Current and next class from the server clock (Asia/Kolkata), plus **other
  classes running in the same time slot**, computed from the timetable slots.
- Course code is shown once; `(CODE)` is appended only when the name differs.
- Class timetable upload (PDF/CSV) with inline progress; the chosen filename is
  remembered so the latest upload survives a reload. *Clear All* tolerates an
  empty `204` response.

### Vacant room lookup

- Live mode (server clock) or manual `day` + `time`.
- Vacant and occupied lists, all-rooms list, and weekend / lunch / after-hours
  messaging. Reports `has_timetable` instead of failing when nothing is uploaded.

### Attendance

- Daily banner with a live IST clock, classes scheduled today, how many are
  unmarked, and an at-risk list with "attend next N".
- Subject cards in a compact grid (2 per row mobile, 3 desktop): course, status
  badge, large percentage, attended/total, thin progress bar, skip/recover
  advice, and per-period chips for multi-period days.
- Colour thresholds: green ≥ target, orange within 10 below, red below.
- **P**/**A** are disabled with the tooltip *"No class scheduled today"* when
  there is no class; **C** is always available.
- Optimistic marking with a toast and a one-tap **Undo** (deletes the record).
- Details modal: month calendar with prev/next, today ringed, colour-coded days,
  a blue border for multi-period/extra entries, and editing of past dates.
- Subjects | History sub-tabs. Subjects sync from the uploaded timetable.
- Attendance target drives the risk colouring (stored in `localStorage` — see
  [Known gaps](#known-gaps)).

### Exam

- **Quick Roll Lookup**: roll prefilled from the signed-in user (cached, with
  `/auth/me` as fallback), *Find Room* button, results as compact cards with
  course code, room, date, day and time. Exams dated today get a blue card and a
  `● TODAY` badge. Duplicate rooms are collapsed and the last result set is
  restored after a refresh.
- Two upload cards — *Exam Timetable* and *Exam Seating Index* — side by side
  while empty, stacked once populated. Each shows its own *"Uploaded (N
  entries)"* with a red Remove behind a confirm dialog. Upload errors appear
  inline and keep the selected file for retry.
- Exam Timetable view: semester/branch filters defaulting to the profile, a
  *Synced with profile* badge, a hint for how many rows are hidden, and rows
  grouped as *Day-1 Monday* with Date | Time | Course Code | Instructor.
- Exam Seating Index view: grouped by date and time with Lecture Hall | Course
  Code | Roll Numbers, 20-row preview and *Show All*.
- Refetches automatically when `profile_version` changes.

---

## Monitoring

Two admin sections — **Web App Monitoring** and **Android App Monitoring** —
each with four subsections, plus a scan-history tab across both.

| Subsection | What it reports |
|---|---|
| Health & Performance | Request counts and latency from the app's own Prometheus registry, crash-free rate per platform, data freshness |
| User Activity | Active users, sessions, new vs returning, day-N retention, countries, app versions, hourly volume |
| Security | Integrity signals (root / emulator / tamper) and auth events, by kind |
| Feedback | Volume, VADER sentiment distribution, topic mix, reply rate |

### Turning it on

Nothing is on by default. The dashboards say *"no data yet"* rather than showing
zeros, so an unconfigured deployment is empty rather than misleading.

```bash
# 1. Generate a pepper. Required - the API refuses telemetry with the default.
python -c "import secrets; print(secrets.token_hex(32))"

# 2. Set it and switch ingestion on.
echo 'TELEMETRY_PEPPER=<the value above>' >> .env
echo 'TELEMETRY_ENABLED=true'           >> .env

# 3. Bring up the metrics stack.
docker compose --profile monitoring up -d
```

`/metrics` is served by default (`METRICS_ENABLED=true`) and needs no telemetry.

### Compose profiles

| Profile | Adds | Extra RAM | Use when |
|---|---|---|---|
| *(default)* | postgres, backend, frontend | — | Normal operation |
| `monitoring` | + Prometheus, node_exporter | ~400 MB | 2–4 GB VPS |
| `monitoring-full` | + cAdvisor, blackbox_exporter | ~1.5 GB | 8 GB+ VPS |
| `rollup` | + standalone hourly rollup worker | ~50 MB | Multiple backend replicas |

None of the monitoring ports are published to the host. Prometheus reaches the
exporters over the compose network; exposing them would put internal route names
and request counts on the open internet.

Verify collection actually works — a valid config and a working scrape are
different claims:

```bash
# From the host, if you publish Prometheus; otherwise pipe it into a container
# already on the compose network (which is the default setup):
Get-Content backend/backend/tools/check_prometheus.py -Raw |
  docker compose exec -T -e PROMETHEUS_URL=http://prometheus:9090 backend python -
```

### The hourly rollup

Volume charts and every future AI scan read `event_hourly`, not the raw `event`
table — that is what keeps a 90-day comparison cheap enough to run inside a
scan's time budget.

It **recomputes** rather than accumulating. Each run deletes the buckets in its
window and re-derives them from `event`, which makes it idempotent and
self-healing after a crash. An accumulating counter has no reconciliation path:
miss a window or double-run once and every dashboard inherits the error forever.

```bash
# One-off rebuild (this is also the "Rebuild rollup" button in the UI)
docker compose exec backend python -m features.monitoring.rollup --hours 48

# Apply the 90-day retention window as well
docker compose exec backend python -m features.monitoring.rollup --prune
```

### What is deliberately not there

- **No Android client exists.** The four Android subsections read *"awaiting
  first data"* and say which endpoint to point a build at. Rendering zeroes
  would be indistinguishable from a healthy app.
- **No AI scans yet.** The *Scan now* buttons are rendered but disabled, with a
  tooltip explaining that `SCAN_ENABLED` is off. The database tables, the scan
  allowlist and the history/incident-log read path exist and are populated by
  nothing yet. See `docs/observability/ARCHITECTURE.md` for the design.
- **No revenue.** Purchases are recorded with a verified/unverified split and
  every figure states which portion is verified. With `ENABLE_STORE_VERIFY=false`
  (the default) the unverified total is labelled a claim, not revenue.

### Privacy

The monitoring tables are the only place in this app that stores anything about
users that is not already in the `user` table.

- **No IP addresses.** A truncated HMAC is kept for rate limiting and nothing
  else.
- **No user ids.** `user_hash` is HMAC-SHA256 with a server-side pepper, so it
  cannot be reversed from the table alone. Rotating the pepper pseudonymises all
  history at once.
- **No client-settable identity.** There is no field anywhere in the collector
  schema a client can use to name a user — a client that could set its own
  identity could forge activity for anyone.
- **No free-text props.** `props` is a flat map of scalars, count- and
  length-capped, and is never rendered.

---

## API reference

All paths are relative to `http://127.0.0.1:8001`. 🔒 requires
`Authorization: Bearer <token>`.

### Health

| Method | Path | Notes |
|---|---|---|
| `GET` | `/health` | `{"status":"ok"}` |

### Auth

| Method | Path | Body / notes |
|---|---|---|
| `POST` | `/auth/signup` | `{first_name, last_name, gender, programme, semester, branch, username, roll_number, email, password}` |
| `POST` | `/auth/verify-email` | `{email, code}` |
| `POST` | `/auth/resend-code` | `{email}` |
| `POST` | `/auth/login` | OAuth2 form: `username`, `password` → `{access_token}` |
| 🔒 `GET` | `/auth/me` | Current user |
| 🔒 `POST` | `/auth/logout` | Client-side token removal |

### Profile

| Method | Path | Notes |
|---|---|---|
| 🔒 `GET` | `/profile/` | Programme, semester, branch, electives, branch-change state |
| 🔒 `PUT` | `/profile/` | Update any profile field; branch is normalised |
| 🔒 `GET` | `/profile/options` | Branch list, programmes, semester labels |
| 🔒 `POST` | `/profile/branch-change` | `{from_branch?, to_branch, reason?}` |
| 🔒 `DELETE` | `/profile/branch-change` | Clear any pending request |

### Timetable

| Method | Path | Notes |
|---|---|---|
| 🔒 `POST` | `/timetable/upload` | Multipart PDF/CSV → also syncs attendance courses |
| 🔒 `POST` | `/timetable/debug/parse-timetable` | Raw extraction + parsed result |
| 🔒 `GET` | `/timetable/slots` | All slots (times serialised as `HH:MM`) |
| 🔒 `GET` | `/timetable/options` | Branches, semesters and courses found in the data |
| 🔒 `PUT` | `/timetable/slot/{id}` | Edit one slot |
| 🔒 `DELETE` | `/timetable/` | Clear all slots |

### Schedule

| Method | Path | Notes |
|---|---|---|
| 🔒 `GET` | `/schedule/now` | `current_class`, `next_class`, `current_time`, `message` |
| 🔒 `GET` | `/schedule/courses/extra` | Extra courses |
| 🔒 `POST` | `/schedule/courses/extra` | `{code, name, semester, branch}` |
| 🔒 `DELETE` | `/schedule/courses/extra/{code}` | Remove |

### Rooms

| Method | Path | Notes |
|---|---|---|
| `GET` | `/rooms/vacant?mode=live` | Server clock |
| `GET` | `/rooms/vacant?mode=manual&day=Mon&hour=10:30` | Manual override |
| `GET` | `/rooms/all` | Every hall in the timetable |

### Attendance

| Method | Path | Notes |
|---|---|---|
| 🔒 `POST` | `/attendance/` | `{course_id, date, status}` — upsert |
| 🔒 `GET` | `/attendance/summary` | Overall + per-course, scoped to your subjects |
| 🔒 `GET` | `/attendance/subjects` | Subjects synced from the timetable |
| 🔒 `GET` | `/attendance/course/{id}` | Summary **plus** date-by-date `calendar` |
| 🔒 `GET` | `/attendance/records?course_id=` | Raw records |
| 🔒 `GET` | `/attendance/sync` | Re-run timetable → course sync |
| 🔒 `DELETE` | `/attendance/{id}` | Delete a record |

### Exam

| Method | Path | Notes |
|---|---|---|
| 🔒 `POST` | `/exam/timetable/upload` | Mid-sem timetable PDF/CSV |
| 🔒 `POST` | `/exam/seating/upload` | Seating index PDF/CSV |
| 🔒 `POST` | `/exam/upload` | Legacy alias of the seating upload |
| 🔒 `GET` | `/exam/timetable` | Day-grouped, filtered to your profile |
| 🔒 `GET` | `/exam/seating` | Day-grouped seating rows |
| 🔒 `GET` | `/exam/lookup?roll=` | Three-rule lookup; reports which rules ran |
| 🔒 `GET` | `/exam/quick-lookup?roll=` | Unfiltered, only date/room/course code |
| 🔒 `GET` | `/exam/pdf?roll=` | Personalised PDF download |
| 🔒 `GET` | `/exam/status` | Row counts, drives the upload badges |
| 🔒 `DELETE` | `/exam/timetable` · `/exam/seating` | Clear |
| 🔒 `POST` | `/exam/debug/parse-exam` | Raw extraction + parsed result |

### Feedback

| Method | Path | Auth | Notes |
|---|---|---|---|
| 🔒 `POST` | `/feedback/` | User | `{message, name?, phone?, email?, subject?, file?}` |
| 🔒 `GET` | `/feedback/mine` | User | Own submissions + admin replies |
| 🔒 `GET` | `/feedback/responses` | Admin | All submissions + admin replies |
| 🔒 `POST` | `/feedback/{id}/reply` | Admin | `{message}` — appears under student's entry |
| `POST` | `/feedback/ingest` | Webhook | Email ingestion — see [Email-to-Feedback](#email-to-feedback) |

### OCR (optional)

`POST /ocr/extract/timetable`, `POST /ocr/extract/exam`,
`POST /ocr/debug/extract-text`, `GET /ocr/models`.

### Telemetry ingest

Unauthenticated by necessity — a browser beacon and a crashing Android process
cannot present a session. Returns **503** unless `TELEMETRY_ENABLED=true`.

| Method | Path | Notes |
|---|---|---|
| `POST` | `/collect/events` | `{"platform":?, "events":[{event_name, platform, session_id, props?, app_version?, os_version?, device_model?, country?, ts?}]}`. Always 200 with `{accepted, rejected}` — a partially-bad batch must not make clients retry the good events forever |
| `POST` | `/collect/crash` | `{kind, session_id, fingerprint, exception_type?, message?, stack_trace?, fatal?, ...}` |
| `POST` | `/collect/security-signal` | `{kind: root_detected\|emulator_detected\|tamper_detected, blocked?}`. Recorded as an observation, never used to refuse a request |

Event names are an **allowlist** (`ALLOWED_EVENTS` in `collector.py`). Unknown
names are rejected with a generic message — echoing "xyz is not in the allowlist"
would turn the endpoint into an oracle for enumerating what the app records.
`props` is truncated rather than rejected, and capped at 12 keys.

### Monitoring (admin only)

Every endpoint below requires an admin token. Students get **403**, anonymous
**401**.

| Method | Path | Notes |
|---|---|---|
| 🔒 `GET` | `/monitoring/subsections` | The canonical eight. The UI renders from this rather than a local copy, so a button cannot exist without a backend counterpart |
| 🔒 `GET` | `/monitoring/overview` | `?days=&platform=` — everything the panels need in one round trip and one consistent window |
| 🔒 `GET` | `/monitoring/health` | `?days=&platform=` — Prometheus-derived request/latency figures plus crash-free rates |
| 🔒 `GET` | `/monitoring/feedback` | `?days=` — volume, sentiment, topics. Read-only; Feedback Responses is unaffected |
| 🔒 `GET` | `/monitoring/monetisation` | `?days=` — purchases and ad revenue with the verified/unverified split |
| 🔒 `GET` | `/monitoring/history` | `?subsection=&limit=` — scans, the derived incident log, and the tool-call audit |
| 🔒 `POST` | `/monitoring/rollup` | `?lookback_hours=` — rebuild the hourly rollup now instead of waiting for the timer |

### Metrics

| Method | Path | Notes |
|---|---|---|
| `GET` | `/metrics` | Prometheus exposition. Route **templates** (`auth/login`), not concrete paths; status is bucketed to `2xx`/`4xx`/`5xx`; no user identifiers. Excludes itself from its own counters |

---

## Data model

| Table | Purpose | Notable columns |
|---|---|---|
| `user` | Account | `email` (unique), `username` (unique), `roll_number`, `password_hash`, `is_email_verified` |
| `user_profile` | Per-user settings | `user_id`, `programme`, `semester`, `branch`, `elective_codes` (JSON), `attendance_target`, `original_branch`, `branch_changed_at`, `branch_change_requested`, `requested_branch` |
| `course` | Markable subject | `code` (unique), `name`, `semester`, `branch`, `is_elective`, `is_extra` |
| `attendance_record` | One mark | `course_id`, `date`, `status` |
| `timetable_slot` | Weekly class | `day`, `start_time`, `end_time`, `room`, `course_code`, `branch_or_program`, `semester` |
| `exam_seating` | Seating index row | `roll_start_prefix`, `roll_start_num`, `roll_end_num`, `room`, **`seating_date`**, `start_time`, `end_time`, `course_code`, `branch`, `semester`, `is_extra` |
| `mid_sem_schedule` | Exam timetable row | **`schedule_date`**, `start_time`, `end_time`, `course_code`, `room`, `branch`, `semester`, `group` |

### Monitoring tables

Ten tables, all additive. `user_hash` is an HMAC with a server-side pepper, never
a plain hash — see [Privacy](#privacy) above for why that distinction is load-bearing.

| Table | Grain | Notes |
|---|---|---|
| `event` | One thing a user did | Raw. High cardinality, expires after `RETENTION_DAYS` (90) |
| `event_hourly` | Hour × event_name × dimensions | **What every dashboard and every future scan reads.** Dimensions are `''` rather than NULL, because Postgres treats NULLs as distinct in a unique index and the constraint would silently never fire |
| `monitoring_session` | One app/web session | The source of truth for DAU/WAU/MAU and retention. Not deleted by `prune` |
| `purchase` | One transaction | `transaction_id` unique, so a replayed receipt is rejected. `verified` is the column that matters |
| `ad_event` | One impression or click | eCPM is derived from these, never accepted from the client |
| `crash_report` | One crash or ANR | `session_id` is what makes a session-based crash-free rate possible. `stack_trace` is untrusted text |
| `security_event` | One security occurrence | `ip_hash` is truncated; the raw address is never stored |
| `scan_result` | One AI scan verdict | Never overwritten. **Empty until scans are enabled** |
| `status_transition` | One status change | The incident log is *derived* from this, not stored — an open incident has no end time |
| `tool_call_audit` | One tool call by one scan | What makes "the scan never invented a number" checkable rather than a claim |

`seating_date` and `schedule_date` are declared with an explicit `sa_column`
because `date` would otherwise collide with `datetime.date` in SQLAlchemy's column
naming. `User` and `UserProfile` are linked by a foreign key only — a
bidirectional `Relationship` caused mapper-initialisation errors.

---

## How the exam system works

Both PDFs come from overlapping text layers, so the parsers are written as state
machines rather than fixed column reads.

**Seating index** (`MID SEM Indexing …-print.PDF`) — columns
`S. No. | Lecture Hall | Course Code | Roll Numbers | …`, with day lines such as
`21.09.2026(Monday)` and time lines such as `08:00 AM - 10:00 AM`. A room is
inherited by continuation rows, roll cells mix ranges (`26BCS042 to 26BCS113`)
with loose lists (`23BCS125, 23BCS197`), and hall codes like `CR103` look like
course codes. Handled:

- date/room/time context threaded **across table boundaries**, so continuation
  tables keep their day
- `10.30AM-12.30PM` meridiem parsing, including shorthand like `3.30-5.30pm`
  where only the closing time carries the meridiem; impossible ranges
  (`22.30-12.30PM`) are discarded
- month normalisation (`29th Sept 2025`, `21.09.2026(Monday)`, ISO)
- batch suffixes (`NS1001 (Batch-A)`) and slash-courses (`CS8031/CS8032`)
- open electives (`OE3E33`) flagged `is_extra`
- hall codes excluded from course extraction
- outlier dates dropped (garbled text can yield e.g. `2030-05-30`)
- rows whose course *and* roll range are unreadable are **skipped and counted**,
  never guessed — a fabricated row would corrupt lookups

**Mid-sem timetable** — columns `Date | Time | Course Code | Semester` with
`DAY 1` / `DAY 2` markers. It carries **no room column**, so halls are joined in
from the seating index on course code + date, preferring the hall that covers the
most students on that date.

The current PDFs yield **705 seating rows and 75 timetable rows** with zero
unknown course codes.

### The three lookup rules

`GET /exam/lookup?roll=` applies, in order:

1. **Profile sync** — rows are filtered to your branch family, semester and
   elective codes.
2. **Continuous range → exact room** — an unbroken roll range (≤ 400 students)
   gives the precise hall.
3. **Extra courses** — `OE…` rows are shared across branches. They are filtered
   by your opted-in electives, and when the index carries no hall the room is
   estimated from the timetable, then from the most common hall in that slot.

Each returned exam reports which `rule` produced it, so the UI can distinguish
exact matches from estimates.

---

## How the frontend maps to the backend

The Attendance tab is built from endpoints that exist, rather than endpoints
that were planned. Where a screen needs a value the API does not expose, it is
derived on the client:

| Screen needs | Derived from |
|---|---|
| Daily banner (classes today, unmarked, IST clock) | `/schedule/now`, `/timetable/slots`, `/attendance/records` |
| At-risk list | `/attendance/summary` (`must_attend`) |
| History list | `/attendance/records` |
| Month calendar | `/attendance/course/{id}` → `calendar`, filtered by month |
| "Class today?" gate on P/A | `/timetable/slots` matched to today's weekday |
| Attendance target | `localStorage` |
| Semester/branch exam filters | `/exam/timetable` filtered client-side |
| Roll prefill | cached `user_roll`, falling back to `/auth/me` |

`tools/replay_session.py` reconstructs the pre-deletion frontend from an exported
session log — useful if you ever need to recover deleted UI work.

---

## Testing

```bash
cd backend/backend
python -m pytest tests/ -q          # 225 passed
```

| File | Covers |
|---|---|
| `test_exam_parser.py` | Times, dates, course codes, roll ranges, branch/semester inference, profile filter |
| `test_endpoints.py` | Every GET endpoint returns non-5xx; day grouping, scoping, PDF |
| `test_auth.py` | Domain validation, OAuth2 form, 401 handling, profile scoping |
| `test_verification.py` | Signup → OTP → login, 10-minute expiry, resend, duplicates |
| `test_timetable_flow.py` | Upload → parse → subject sync → live schedule → vacant rooms → clear |
| `test_room_join.py` | Seating rooms joined onto timetable rows |
| `test_profile_and_lookup.py` | Profile normalisation, continuous-range rule |
| `test_attendance.py` `test_overlap.py` `test_rooms.py` `test_schedule.py` `test_roll_parse.py` `test_timetable_parser.py` | Service-level units |

Tests default to a scratch SQLite file, so they never touch your development
database. **Run them against PostgreSQL too** — SQLite is permissive where
Postgres is not, and a SQLite-only suite cannot catch a migration that breaks
production:

```bash
# fast loop, no service needed
cd backend/backend && python -m pytest -q

# the job that actually gates a database change
docker run -d --name cp-test -e POSTGRES_USER=campuspilot \
  -e POSTGRES_PASSWORD=campuspilot -e POSTGRES_DB=campuspilot_test \
  -p 5432:5432 postgres:16-alpine
cd backend/backend
set TEST_DATABASE_URL=postgresql+psycopg://campuspilot:campuspilot@localhost:5432/campuspilot_test
python -m pytest -q
```

Tests that only mean something on PostgreSQL (constraint enforcement, dialect
DDL) carry the `postgres` marker and are skipped on the SQLite run. CI runs only against PostgreSQL. Migrate a SQLite file with ``docker compose run --rm backend python tools/migrate_sqlite_to_postgres.py`` if you need to move an existing database.
both, plus an `alembic downgrade/upgrade` round-trip and `alembic check` for
model/migration drift.

### Migrating an existing SQLite database

One-shot, and deliberately explicit — a data migration should never be something
you can do by accident.

```bash
docker compose up -d postgres
docker compose run --rm backend python -m alembic -c /app/backend/alembic.ini upgrade head

# read this output before writing anything
docker compose run --rm backend python tools/migrate_sqlite_to_postgres.py \
  --source /app/database/classpilot.db --dry-run

docker compose run --rm backend python tools/migrate_sqlite_to_postgres.py \
  --source /app/database/classpilot.db

docker compose up -d
```

The script preserves primary keys (so foreign keys stay valid), advances the
SERIAL sequences afterwards (or the first signup dies with a duplicate key),
copies parents-first, and verifies every table's row count at the end. It also
reports any NULL it filled from a model default — the existing SQLite file has
rows that violate the current schema, because the old `ADD COLUMN` repair path
dropped `NOT NULL`, and Postgres correctly refuses them.

Frontend:

```bash
cd frontend
npm run build      # production bundle
npm run dev        # dev server on 5173
```

---

## CSV templates

### Class timetable

```csv
day,start_time,end_time,room,course_code,branch_or_program,semester
Mon,09:00,10:00,L-101,CS5031,BTech CSE,5
Mon,11:00,12:00,CR-101,CS5032,BTech CSE,5
Tue,09:00,10:00,L-103,OE3E33,BTech,5
```

All seven columns are required; malformed rows are reported as warnings rather
than failing the upload.

### Seating index

```csv
roll_range,room,date,time,course_code
23BCS001-23BCS050,L-101,2026-09-21,08:00-10:00,CS8036
23BCS051-23BCS100,L-102,2026-09-21,08:00-10:00,CS8036
```

### Mid-sem exam timetable

```csv
date,time,course_code,semester,branch
2025-09-29,10:30AM-12:30PM,CS8036,7,CSE
2025-09-29,03:30PM-05:30PM,OE3E33,7,
```

Roll format is `YYBBBNNN` — `23BCS003` is prefix `23BCS` plus the number `3`.
Ranges are compared numerically within the same prefix.

---

## Email-to-Feedback

Students can send feedback by emailing `feedback@your-domain` (or any address
configured with your mail provider). The app includes:

- **`POST /feedback/ingest`** — Webhook endpoint for SendGrid, Mailgun, Postmark,
  etc. Payload:
  ```json
  {
    "from_email": "student@iiitdmj.ac.in",
    "from_name": "Student Name",
    "subject": "Timetable issue",
    "text": "The timetable upload fails...",
    "html": "<p>The timetable upload fails...</p>",
    "attachments": [
      {"filename": "screenshot.png", "content": "base64...", "content_type": "image/png"}
    ]
  }
  ```
- **IMAP poller** (`tools/imap_feedback_poller.py`) — polls a Gmail/IMAP folder
  every 5 minutes via systemd timer, marks processed mail with a label, and
  posts to `/feedback/ingest`.
- **UI**: Subject shown as title, 📎 badge for attachments, click to expand for
  full message, metadata, and admin replies.

### Setup (SendGrid example)

1. In SendGrid → Settings → Inbound Parse → add hostname `feedback.your-domain`
2. URL: `https://your-api/feedback/ingest`
3. Configure DNS MX for `feedback.your-domain` → SendGrid
4. Emails sent to `anything@feedback.your-domain` arrive as feedback

### Setup (Gmail IMAP)

1. Enable IMAP in Gmail settings
2. Create an App Password (Google Account → Security → App Passwords)
3. Configure `.env` or systemd EnvironmentFile:
   ```
   IMAP_HOST=imap.gmail.com
   IMAP_USER=your-email@gmail.com
   IMAP_PASS=your-app-password
   INGEST_URL=http://localhost:8000/feedback/ingest
   ```
4. Run once: `python tools/imap_feedback_poller.py`
5. For production: `sudo cp deploy/campuspilot-imap-poller.* /etc/systemd/system/`
   `sudo systemctl enable --now campuspilot-imap-poller.timer`

---

## Known gaps

These are real limitations rather than bugs:

1. **Attendance target is browser-local.** There is no `/attendance/target`
   endpoint, so the target lives in `localStorage` and will not follow you to
   another browser or device.
2. **No instructor data.** The exam timetable rows carry no instructor field, so
   the Instructor column renders `—`.
3. **Profile filtering on exam lookup is approximate.** Branch and semester are
   inferred from the roll-number prefix and the course code, so a row's inferred
   branch can disagree with the paper's real branch. The UI states when a
   result set has been narrowed to your profile.
4. **Verification codes are in-memory.** They are lost on backend restart and are
   not shared across workers. Use Redis for multi-worker deployments.
5. **Timetable and exam uploads are global.** One timetable and one seating index
   are shared by every user, which suits a single cohort; per-branch uploads
   would need a scope key.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `Backend offline` dot in the header | Backend is not on port 8000. Start it and reload. Confirm `curl http://127.0.0.1:8000/health` returns `{"status":"ok"}`. |
| `/health` returns 500 at startup | A previous process still holds `classpilot.db`. Stop it, or delete the file — it is recreated with empty tables. |
| Login always 401s | Token not attached, or `SECRET_KEY` changed after the token was issued. Log out and back in. |
| Signup rejected | Email must end with `@iiitdmj.ac.in`; username and roll must be unique. |
| No verification email | Check `SMTP_USER`/`SMTP_PASSWORD`. Gmail requires an app password. Use *Resend Code* after 60 s. |
| Upload says "no rows found" | The file is a 0-byte download, or a scanned image with no text layer. Re-download and check the size. |
| Live Schedule / Vacant Rooms empty | No class timetable uploaded yet — **Live Schedule → Timetable**. |
| Attendance has no subjects | Subjects sync from the timetable; upload it, then *Refresh*. |
| `401` on every request in dev | The Vite proxy points at 8000. `vite.config.ts` targets 8000 — confirm the proxy is not being shadowed by a stale `vite.config.js`. |
| Port already in use | `netstat -ano | findstr :8001` then `taskkill /f /pid <PID>`. |

---

## License

MIT — built for students, by students.