# CampusPilot — ClassPilot Academic Module

> Built in ~5.5 hours. Priorities: runs on first try, simple/debuggable code, testable phases.

---

## Tech Stack
- **Backend**: Python 3.11+, FastAPI, SQLModel, SQLite, pdfplumber, reportlab, pandas
- **Frontend**: React 18 + Vite, inline Tailwind CSS via CDN (no custom CSS files)

---

## Folder Structure
```
CampusPilot/
├── requirements.txt
├── .env.example
├── backend/
│   └── backend/
│       ├── main.py                 # FastAPI app, CORS, router includes
│       ├── database.py             # Engine, session, create_db
│       ├── models.py               # SQLModel tables
│       ├── config.py               # Settings from .env
│       ├── routes/
│       │   ├── attendance.py       # POST/GET/DELETE attendance
│       │   ├── timetable.py        # PDF/CSV upload, debug, edit
│       │   ├── profile.py          # GET/PUT profile
│       │   ├── schedule.py         # GET /now, extra courses
│       │   ├── rooms.py            # Vacant rooms live/manual
│       │   └── exam.py             # Exam upload, lookup, PDF
│       ├── services/
│       │   ├── attendance_service.py
│       │   ├── timetable_parser.py
│       │   ├── schedule_service.py
│       │   ├── room_service.py
│       │   ├── exam_parser.py
│       │   └── exam_pdf.py
│       ├── utils/
│       │   └── file_prompt.py      # Upload validation
│       ├── scripts/
│       │   └── seed.py             # Sample data
│       ├── tests/
│       │   ├── test_attendance.py
│       │   ├── test_overlap.py
│       │   ├── test_roll_parse.py
│       │   ├── test_timetable_parser.py
│       │   ├── test_schedule.py
│       │   └── test_rooms.py
│       └── uploads/                # Runtime uploads
├── database/                       # SQLite file (classpilot.db)
├── frontend/
│   ├── package.json
│   ├── vite.config.js
│   ├── index.html
│   ├── .env.example
│   └── src/
│       ├── main.jsx
│       ├── App.jsx
│       ├── api.js
│       └── components/
│           ├── Spinner.jsx
│           ├── ErrorBanner.jsx
│           ├── StatusCard.jsx
│           ├── FileUpload.jsx
│           ├── LiveSchedule.jsx
│           ├── VacantRoomLookup.jsx
│           ├── Attendance.jsx
│           └── ExamSeating.jsx
└── README.md
```

---

## Features

| Feature | Endpoints | Description |
|---------|-----------|-------------|
| **A. Attendance** | `POST /attendance`, `GET /attendance/summary`, `GET /attendance/course/{id}`, `DELETE /attendance/{id}` | Mark Present/Absent/Cancelled, per-course & overall %, status flags, can_miss, must_attend |
| **B. Live Schedule** | `GET /schedule/now`, `PUT /profile`, `POST /timetable/upload`, `POST /schedule/courses/extra` | System-time current/next class, PDF/CSV timetable upload, profile + electives, extra courses |
| **C. Vacant Rooms** | `GET /rooms/vacant?mode=live`, `GET /rooms/vacant?mode=manual&day=Mon&hour=10:00` | Live + manual lookup, occupied rooms with course, lunch/weekend/after-hours handling |
| **D. Exam Seating** | `POST /exam/upload`, `GET /exam/lookup?roll=XXX`, `GET /exam/pdf?roll=XXX` | PDF/CSV parser, roll range lookup, personalized ReportLab PDF |

---

## Quick Start

### Prerequisites
- Python 3.11+
- Node 18+
- Ports 8000 (backend) and 5173 (frontend) free

### Quick Start (Recommended) — One Command
```powershell
# PowerShell (Windows) - creates venv, installs deps, seeds DB, starts both servers
.\start_campuspilot.ps1
```
```cmd
:: Batch file (Windows) - same as above
start_campuspilot.bat
```

### Manual Start (if you prefer separate terminals)

#### Backend (with virtual environment)
```bash
cd CampusPilot
# Create venv (first time only)
python -m venv backend/backend/.venv
# Activate & install
backend/backend/.venv/Scripts/activate
pip install -r requirements.txt
# Seed & run
cd backend/backend
python scripts/seed.py
uvicorn main:app --reload --port 8000
```

#### Frontend
```bash
cd CampusPilot/frontend
npm install
npm run dev
# Opens http://localhost:5173
```

---

## Environment Variables

### Backend (`backend/backend/.env`)
```env
DATABASE_URL=sqlite:///../../database/classpilot.db
TIMEZONE=Asia/Kolkata
COLLEGE_START=09:00
COLLEGE_END=17:00
LUNCH_START=13:00
LUNCH_END=14:00
ATTENDANCE_SAFE=75
ATTENDANCE_WARNING=65
MAX_UPLOAD_MB=10
ALLOWED_EXTENSIONS=.pdf,.csv
```

### Frontend (`frontend/.env`)
```env
VITE_API_URL=http://localhost:8000
```

---

## API Reference

### Health
- `GET /health` → `{"status":"ok"}`

### Attendance
- `POST /attendance` — Body: `{course_id, date, status: Present|Absent|Cancelled}`
- `GET /attendance/summary` — Overall + per-course
- `GET /attendance/course/{id}` — Single course detail
- `DELETE /attendance/{id}` — Delete record

### Timetable
- `POST /timetable/upload` — Multipart file (PDF/CSV)
- `POST /timetable/debug/parse-timetable` — Raw extraction + parsed
- `DELETE /timetable` — Clear all slots
- `PUT /timetable/slot/{id}` — Edit slot
- `GET /timetable/slots` — List all

### Profile
- `GET /profile` — Current profile
- `PUT /profile` — Update semester/branch/electives

### Schedule
- `GET /schedule/now` — Current + next class (live)
- `POST /schedule/courses/extra` — Add extra course
- `GET /schedule/courses/extra` — List extra courses
- `DELETE /schedule/courses/extra/{code}` — Remove extra

### Rooms
- `GET /rooms/vacant?mode=live` — Live vacant rooms
- `GET /rooms/vacant?mode=manual&day=Mon&hour=10:30` — Manual override
- `GET /rooms/all` — All rooms

### Exam
- `POST /exam/upload` — Exam seating PDF/CSV
- `POST /exam/debug/parse-exam` — Raw + parsed
- `GET /exam/lookup?roll=23BCS100` — Exam details
- `GET /exam/pdf?roll=23BCS100` — Download PDF

---

## Data Models

| Model | Key Fields |
|-------|------------|
| **Course** | `code`, `name`, `semester`, `branch`, `is_elective`, `is_extra` |
| **AttendanceRecord** | `course_id`, `date`, `status` (Present/Absent/Cancelled) |
| **TimetableSlot** | `day`, `start_time`, `end_time`, `room`, `course_code`, `branch_or_program`, `semester` |
| **UserProfile** | `semester`, `branch`, `elective_codes` (JSON list) |
| **ExamSeating** | `roll_start_prefix`, `roll_start_num`, `roll_end_num`, `room`, `exam_date`, `start_time`, `end_time`, `course_code` |

> Roll format: `23BCS003` → prefix `23BCS` + integer `3`. Ranges compared numerically within same prefix.

---

## Testing

```bash
# Backend tests
cd CampusPilot/backend/backend
python -m pytest tests/ -v

# Run all test files:
# test_attendance.py      (11 tests)
# test_overlap.py         (7 tests)
# test_roll_parse.py      (14 tests)
# test_timetable_parser.py (12 tests)
# test_schedule.py        (10 tests)
# test_rooms.py           (9 tests)
# Total: 63 tests
```

---

## Sample Data (seeded via `scripts/seed.py`)

- **Courses**: CS301, CS302, CS303, CS304 (elective), MA201, EE101, HS101 (extra)
- **Attendance**: Mixed present/absent/cancelled for CS301-303
- **Timetable**: 14 slots across Mon-Fri for CSE Sem 5
- **Profile**: Semester 5, CSE, electives=[CS304]
- **Exams**: 5 seating ranges for 23BCS001-23BCS100

---

## CSV Templates

### Timetable (`sample_timetable.csv`)
```csv
day,start_time,end_time,room,course_code,branch_or_program,semester
Mon,09:00,10:00,L-101,CS301,CSE,5
Mon,10:00,11:00,L-102,CS302,CSE,5
Tue,09:00,10:00,L-102,CS302,CSE,5
Tue,10:00,11:00,L-101,CS301,CSE,5
```

### Exam Seating (`sample_exam.csv`)
```csv
roll_range,room,date,time,course_code
23BCS001-23BCS050,L-101,2026-12-15,09:00-12:00,CS301
23BCS051-23BCS100,L-102,2026-12-15,09:00-12:00,CS301
23BCS001-23BCS100,CR-201,2026-12-17,09:00-12:00,CS302
23BCS001-23BCS100,L-201,2026-12-19,14:00-17:00,CS303
23BCS001-23BCS030,CR-202,2026-12-21,09:00-12:00,CS304
```

---

## V2 Upgrades (Post-5.5h)
- [ ] WebSocket live updates instead of 60s polling
- [ ] Role-based auth (student/faculty/admin)
- [ ] Multi-college support
- [ ] Timetable conflict detection on upload
- [ ] Exam clash detection
- [ ] Offline-first PWA
- [ ] Export attendance to Excel

---

## License
MIT — Built for students, by students.