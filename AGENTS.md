# CampusPilot — Agent Instructions

This is a full-stack campus management application with a **Python/FastAPI backend** and a **React/Vite frontend**. The frontend uses a **four-module lazy-loaded architecture** (student-ug, student-pg, admin, faculty) with Vite multi-entry builds.

---

## Project Structure

```
CampusPilot/
├── backend/                 # FastAPI backend (Python 3.10+)
│   ├── app/
│   │   ├── core/            # Config, database, deps, files
│   │   ├── features/        # Domain features (auth, timetable, exam, schedule, etc.)
│   │   ├── models.py        # SQLModel models
│   │   └── main.py          # FastAPI app entry
│   ├── alembic/             # Database migrations
│   ├── requirements.txt
│   └── .env.example
├── frontend/                # React 18 + Vite + TypeScript
│   ├── src/
│   │   ├── core/App.tsx     # Root router (role-based module selection)
│   │   ├── shared/          # Pure shared layer (zero feature imports)
│   │   │   ├── auth/        # AuthWrapper + all auth screens
│   │   │   ├── components/  # Shared UI components
│   │   │   ├── hooks/       # Shared hooks (useProfile, useLiveDay, etc.)
│   │   │   ├── lib/         # Utilities (storage, time, sync, passkey, normalise)
│   │   │   ├── types/       # Shared API types
│   │   │   ├── constants.ts # GROUP_CLASSROOM_TABS, NAV_TABS, programmeGroupOf
│   │   │   └── features/profile/Profile.tsx
│   │   ├── modules/         # Four lazy-loaded modules
│   │   │   ├── student-ug/  # UG programmes (BTech, BDes)
│   │   │   ├── student-pg/  # PG programmes (MTech, MDes), PhD
│   │   │   ├── admin/       # Admin panel + monitoring
│   │   │   └── faculty/     # Placeholder
│   │   ├── api.ts           # API client (re-exports from shared/)
│   │   └── main.tsx         # App entry point
│   ├── vite.config.ts       # Multi-entry build config
│   ├── tsconfig.json        # Path aliases (@/, @shared/, @modules/)
│   └── package.json
├── deploy/                  # systemd service files
├── ops/                     # Prometheus/Grafana configs
├── docs/                    # Architecture, monitoring, roadmap
├── scripts/                 # Dev/ops scripts
└── docker-compose.yml       # Full stack (backend, frontend, DB, Prometheus, Grafana)
```

---

## Key Technologies

| Layer | Stack |
|-------|-------|
| **Backend** | FastAPI, SQLModel, PostgreSQL (prod) / SQLite (dev), Alembic, Uvicorn |
| **Frontend** | React 18, TypeScript, Vite, Tailwind CSS v4 (PostCSS), React Router |
| **Auth** | JWT + WebAuthn (passkeys), HttpOnly cookies |
| **Monitoring** | Prometheus + Grafana, custom scan agent |
| **Container** | Docker Compose (backend, frontend, postgres, prometheus, grafana) |

---

## Common Commands

### Backend (from `CampusPilot/backend/`)

```bash
# Setup
python -m venv .venv && .venv/Scripts/activate     # Windows
pip install -r requirements.txt
cp .env.example backend/backend/.env               # Fill SECRET_KEY + SMTP

# Run dev server
cd backend && python -m uvicorn main:app --port 8000 --reload

# Migrations (run from backend/ where alembic.ini lives)
python -m alembic -c alembic.ini upgrade head
python -m alembic -c alembic.ini revision --autogenerate -m "description"

# Tests
cd backend/backend && python -m pytest tests/ -q

# Type check (if using pyright/mypy)
# npx pyright  # or your preferred tool
```

### Frontend (from `CampusPilot/frontend/`)

```bash
# Setup
npm install

# Dev server (proxies /api to localhost:8000)
npm run dev

# Type check
npx tsc --noEmit

# Lint
npm run lint
npm run lint:fix

# Format
npm run format

# Unit tests
npm run test

# Production build
npm run build

# Preview production build
npm run preview
```

### Full Stack (Docker)

```bash
# From CampusPilot/
docker compose up -d --build

# View logs
docker compose logs -f backend
docker compose logs -f frontend
```

---

## Frontend Architecture Rules

### Module Routing (`src/core/App.tsx`)
- Root router selects module by `user.role` and `programmeGroupOf(user.programme)`
- **UG** → `student-ug` module (Live Schedule, Attendance, Vacant Rooms, Exam, Teams, Feedback)
- **PG/PhD** → `student-pg` module (Live Schedule, Exam, Teams, Feedback)
- **admin** → `admin` module (Admin Panel, Monitoring, Profile)
- **faculty** → `faculty` module (placeholder)

### Shared Layer Purity
- **Zero imports from `features/`** in `src/shared/` — verified by `grep -r "from.*features" src/shared`
- All shared components/hooks/types are importable by any module without pulling feature code
- Use Vite aliases: `@shared/*`, `@modules/*`, `@/*`

### Feature Gating
- Single source of truth: `GROUP_CLASSROOM_TABS` in `src/shared/constants.ts`
- Modules **import** this, never duplicate it
- UG: `['live', 'attendance', 'vacant', 'exam']`
- PG/PhD: `['live', 'exam']`

### Error Isolation
- Each module wrapped in `ModuleErrorBoundary` — crash in one module doesn't white-screen the app
- Header, footer, other modules remain functional

### Lazy Loading
- Modules loaded via `React.lazy()` + `Suspense` on first access
- Shared components (Profile, NavIcons) in main chunk
- Module-specific code downloads only when needed

---

## Backend Architecture Rules

### Configuration
- All config through `config.get_settings()` — never hard-code college hours, thresholds, branch lists
- Derived constants (`COLLEGE_START_HOUR`, `DAYS_ORDER`, `BRANCH_OPTIONS`) live in `app/core/config.py`

### Business Logic
- Services in `app/features/<domain>/service.py` — **not** in routes
- Routes validate input and serialize output only

### Database Patterns
- Use `session.exec(select(Model).where(...)).first()` — avoid `session.get()` / `session.add()` (breaks under SQLModel)
- Bulk deletes: `session.exec(delete(Model))` — `session.exec(select(X)).delete()` does **not** exist
- Timestamps: server-side defaults (`server_default=func.now()`) — `Field(default_factory=...)` broken under SQLModel 0.0.22 + Pydantic 2.10

### Auth
- Every endpoint touching user data must declare `get_current_user` dependency
- Returning `400` for bad token is fine; returning `200` to anonymous caller is not

### Adding an Endpoint
1. Service function in `app/features/<domain>_service.py`
2. Pydantic request/response models in route module
3. Route in `app/features/<domain>/routes.py` with `get_current_user` if user data
4. Register in `app/features/<domain>/__init__.py` and include in `main.py`
5. Add to API table in `README.md` and `frontend/src/api.ts`
6. Test happy path **and** 401 path

---

## Database Migrations

```bash
# From CampusPilot/backend/
python -m alembic -c alembic.ini upgrade head
python -m alembic -c alembic.ini revision --autogenerate -m "description"
```

- `create_db_and_tables()` creates missing tables + runs migration pass for `ADD COLUMN`
- For renames/destructive changes: add explicit step to `app/core/database.py`
- Never edit/delete `classpilot.db` by hand in committed changes

---

## Git Workflow

- Branch from `main`, one topic per branch
- Commit messages: imperative mood, explain **why**, not **what**
- Never commit: `database/classpilot.db`, `backend/backend/uploads/`, `.env`, `node_modules/`

---

## Pre-PR Checklist

```bash
# Backend
cd backend/backend && python -m pytest tests/ -q     # must be green

# Frontend
cd frontend && npm run build                          # must succeed
cd frontend && npm run lint                           # must pass
cd frontend && npx tsc --noEmit                       # must pass
```

---

## Environment Variables

### Backend (`backend/backend/.env`)
```
SECRET_KEY=...
DATABASE_URL=postgresql://...  # or sqlite:///classpilot.db
SMTP_HOST=...
SMTP_PORT=...
SMTP_USER=...
SMTP_PASSWORD=...
EMAIL_FROM=...
FRONTEND_ORIGIN=http://localhost:5173
```

### Frontend (`frontend/.env` or Vite config)
```
VITE_DEV_BACKEND=http://127.0.0.1:8000   # Must use 127.0.0.1, not localhost (Windows IPv6 issue)
```

---

## Debugging Tips

### Frontend Module Load
- DevTools Network tab → filter by "module-"
- Each module chunk loads on first access to that role/programme
- Suspense fallback shows spinner while chunk downloads

### Backend Proxy (Vite)
- `vite.config.ts` proxies `/api` to `VITE_DEV_BACKEND` (default `http://127.0.0.1:8000`)
- Backend port **must** match proxy target
- Use `127.0.0.1`, not `localhost` (Windows resolves `localhost` to `::1` first)

### Vite Config Trap
- Keep only **one** `vite.config` file — Vite resolves `vite.config.js` before `vite.config.ts`
- A stale `.js` silently wins and your `.ts` edits do nothing

### Tailwind Is A Build Dependency
- Tailwind v4 builds through `postcss.config.js` → `@tailwindcss/postcss`. There is no CDN script in `index.html`
- All four packages must stay declared in `package.json`: `tailwindcss`, `@tailwindcss/postcss`, `postcss`, `autoprefixer`
- **This fails silently.** With the PostCSS plugin present but `tailwindcss` missing, `@import "tailwindcss"` resolves to nothing and the build *succeeds* while emitting ~3 kB of CSS — an unstyled app with a green tick. It only surfaced when a stray `npm install` pruned the undeclared packages
- Sanity check after any dependency change: the built CSS should be tens of kB, not single digits. `dist/assets/main-*.css` size is the tell

---

## Documentation References

- `MODULE_ARCHITECTURE.md` — Frontend module architecture deep dive
- `docs/LOCAL_DEVELOPMENT.md` — Local dev setup details
- `docs/ROADMAP.md` — Project roadmap
- `docs/PHASE_WISE_TASK_LIST.md` — Phase-wise task breakdown
- `CONTRIBUTING.md` — Original contributing guide
- `START_BACKEND_GUIDE.md` — Backend startup guide

---

## OppFeed Integration

OppFeed (autonomous internship/job discovery & publishing) is integrated into CampusPilot as a backend feature module plus admin and faculty frontend screens.

### Backend
- **Models**: `backend/app/features/oppfeed/models.py` — 9 tables (Opportunity, AgentRun, RunStep, AgentSettings, SourceRule, SearchQuery, OppFeedFeedback, LLMCache, LLMUsage), all in `core` schema
- **Routes**: `backend/app/features/oppfeed/routes.py` — 23 endpoints:
  - `GET/POST /admin/oppfeed/opportunities` — manage opportunities (admin only)
  - `GET/POST/PATCH /admin/oppfeed/runs` — trigger & view agent runs (admin only)
  - `GET/PATCH /admin/oppfeed/settings` — agent configuration (admin only)
  - `GET/POST/PATCH/DELETE /admin/oppfeed/source-rules` — allow/deny domains (admin only)
  - `GET/POST/PATCH/DELETE /admin/oppfeed/search-queries` — search queries (admin only)
  - `GET /admin/oppfeed/llm-status` — LLM provider health (admin only)
  - `GET /admin/oppfeed/opportunities/{id}/feedback` — feedback (admin only)
  - `GET /faculty/oppfeed` — paginated opportunity feed (faculty/student)
  - `GET /faculty/oppfeed/filters` — filter options (faculty/student)
  - `GET /faculty/oppfeed/{slug}` — opportunity detail (faculty/student)
- **Agent**: `backend/app/features/oppfeed/agent/` — LangGraph pipeline for discovery/verification
- **Migration**: `alembic/versions/20261018_0016_oppfeed_models.py`
- **Seed**: `backend/app/features/oppfeed/seed.py` — idempotent dev data

### Frontend
- **Admin**: `frontend/src/modules/admin/features/oppfeed/` — Dashboard, Agent Runs, Agent Run Detail, Opportunities Manager, Agent Settings, LLM Status
- **Faculty**: `frontend/src/modules/faculty/features/oppfeed/` — OppFeedList (paginated cards with filter)
- **API client**: `frontend/src/api.ts` — `oppfeedApi` with 23 methods
- **Types**: `frontend/src/shared/types/api.ts` — 30+ OppFeed interfaces

### Auth
CampusPilot auth is the single source of truth. All OppFeed routes use `get_current_admin` (admin) or `get_current_user` (faculty/student). No separate OppFeed auth, user table, or JWT.

### Environment Variables
Add to `.env`:
```
ENABLE_AGENT=false
ENABLE_SCHEDULER=false
ENABLE_VISION=false
ENABLE_BANNER_GEN=false
ENABLE_AUDIO_SUMMARY=false
NVIDIA_NIM_API_KEY=
OPENROUTER_API_KEY=
OPENAI_API_KEY=
```