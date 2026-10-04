# Essential — Your Campus Assistant

A campus assistant for IIITDM Jabalpur students. Upload the class timetable, the
mid-sem exam timetable and the exam seating index once, and the app answers the
three questions that matter every semester:

- **What class do I have right now?** Live schedule from the system clock.
- **Where is my exam, and when?** Roll-number lookup with rooms and halls.
- **Am I safe on attendance?** Per-subject tracking against your target.

Backend: FastAPI + SQLModel + SQLite. Frontend: React 18 + Vite.

---

## Table of contents

- [Quick start](#quick-start)
- [Environment variables](#environment-variables)
- [Project layout](#project-layout)
- [Features](#features)
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
| Free ports | **8001** (backend), **5173** (frontend) |

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
python -m uvicorn main:app --port 8001
```

The database file and all tables are created automatically on first boot, and
older databases are migrated in place. Check it is alive:

```bash
curl http://127.0.0.1:8001/health     # {"status":"ok"}
```

Interactive API docs: <http://127.0.0.1:8001/docs>

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

Open <http://localhost:5173>. The Vite dev server proxies every backend prefix
(`/auth`, `/profile`, `/schedule`, `/timetable`, `/rooms`, `/attendance`,
`/exam`, `/health`, `/ocr`, `/api`) to `http://localhost:8001`, so the app runs
same-origin and needs no CORS setup.

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
| `DATABASE_URL` | `sqlite:///…/database/classpilot.db` | SQLite location |
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
│   └── classpilot.db             # SQLite (created on first boot)
├── backend/
│   ├── requirements.txt
│   └── backend/
│       ├── main.py               # App, CORS, lifespan, router registration
│       ├── config.py             # Settings + derived constants
│       ├── database.py           # Engine, session, schema creation & migration
│       ├── models.py             # SQLModel tables
│       ├── routes/               # auth, profile, schedule, timetable, rooms,
│       │                         # attendance, exam, deps (bearer auth)
│       ├── services/             # Business logic
│       │   ├── exam_parser.py    # Seating-index + mid-sem PDF parsers
│       │   ├── exam_lookup.py    # Three-rule roll lookup
│       │   ├── exam_pdf.py       # ReportLab PDF generation
│       │   ├── attendance_service.py
│       │   ├── timetable_parser.py
│       │   ├── schedule_service.py
│       │   ├── room_service.py
│       │   └── profile_service.py
│       ├── ocr_engine/           # Optional OCR extraction
│       ├── utils/file_prompt.py  # Upload validation
│       ├── scripts/seed.py       # Demo data
│       ├── tests/                # 225 tests
│       └── uploads/              # Runtime uploads (git-ignored)
├── frontend/
│   ├── index.html                # Title, favicon, Tailwind palette, CSS reset
│   ├── vite.config.js            # Port 5173, proxy → 8001
│   ├── public/
│   │   ├── logo.svg              # Lightbulb lockup + wordmark
│   │   └── logo-icon.svg         # Icon: 9/11/2 rings, smile, teal
│   └── src/
│       ├── main.jsx
│       ├── App.jsx               # Single header, nav, footer
│       ├── api.js                # fetch wrapper + all endpoints
│       ├── constants.js          # Branches, programmes, semesters
│       ├── index.css             # Component classes
│       └── components/
│           ├── AuthWrapper.jsx   # Session context, /auth/me retry
│           ├── LoginForm.jsx
│           ├── SignupForm.jsx
│           ├── VerifyEmail.jsx   # 6-digit OTP + resend cooldown
│           ├── LiveSchedule.jsx  # Schedule | Profile | Timetable
│           ├── Attendance.jsx    # Banner, subject grid, calendar, history
│           ├── ExamSeating.jsx   # Lookup, uploads, timetable + seating views
│           ├── VacantRoomLookup.jsx
│           ├── FileUpload.jsx
│           ├── StatusCard.jsx
│           ├── ErrorBanner.jsx
│           └── Spinner.jsx
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

### OCR (optional)

`POST /ocr/extract/timetable`, `POST /ocr/extract/exam`,
`POST /ocr/debug/extract-text`, `GET /ocr/models`.

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

Tests use a scratch SQLite file configured in `tests/conftest.py`, so they never
touch your development database.

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
| `Backend offline` dot in the header | Backend is not on port 8001. Start it and reload. |
| `/health` returns 500 at startup | A previous process still holds `classpilot.db`. Stop it, or delete the file — it is recreated with empty tables. |
| Login always 401s | Token not attached, or `SECRET_KEY` changed after the token was issued. Log out and back in. |
| Signup rejected | Email must end with `@iiitdmj.ac.in`; username and roll must be unique. |
| No verification email | Check `SMTP_USER`/`SMTP_PASSWORD`. Gmail requires an app password. Use *Resend Code* after 60 s. |
| Upload says "no rows found" | The file is a 0-byte download, or a scanned image with no text layer. Re-download and check the size. |
| Live Schedule / Vacant Rooms empty | No class timetable uploaded yet — **Live Schedule → Timetable**. |
| Attendance has no subjects | Subjects sync from the timetable; upload it, then *Refresh*. |
| `401` on every request in dev | The Vite proxy points at 8000. `vite.config.js` targets 8001 — restart the dev server. |
| Port already in use | `netstat -ano | findstr :8001` then `taskkill /f /pid <PID>`. |

---

## License

MIT — built for students, by students.