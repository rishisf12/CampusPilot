# CampusPilot Local Development Guide

This guide walks you through setting up CampusPilot for local development using **Python 3.10**, **Node.js 20**, **PostgreSQL 16**, and **VS Code** with the integrated terminal.

---

## Prerequisites

| Tool | Version | Install Command / Link |
|------|---------|------------------------|
| **Python** | **3.10.x** (required) | `winget install Python.Python.3.10` or [python.org](https://www.python.org/downloads/release/python-3100/) |
| **Node.js** | 20.x (LTS) | `winget install OpenJS.NodeJS.LTS` or [nodejs.org](https://nodejs.org/) |
| **PostgreSQL** | 16.x | `winget install PostgreSQL.PostgreSQL` or [postgresql.org](https://www.postgresql.org/download/windows/) |
| **Docker Desktop** | Latest | [docker.com](https://www.docker.com/products/docker-desktop/) |
| **Git** | Latest | `winget install Git.Git` or [git-scm.com](https://git-scm.com/) |
| **VS Code** | Latest | `winget install Microsoft.VisualStudioCode` or [code.visualstudio.com](https://code.visualstudio.com/) |

> ⚠️ **Python 3.10 is required** — the project uses features and dependencies not compatible with 3.11+ in the current stack. Verify with `python --version` (should show `3.10.x`).

---

## Repository Structure

```
CampusPilot/
├── docker-compose.yml          # Main compose file (at repo root)
├── .env.example                # Copy to .env and fill in secrets
├── .env.imap.example           # IMAP-specific env vars
├── backend/
│   ├── backend/                # FastAPI application package
│   │   ├── core/               # Database, config, security
│   │   ├── features/           # Feature modules (auth, monitoring, etc.)
│   │   ├── main.py             # FastAPI entry point
│   │   ├── requirements.txt    # Python deps
│   │   ├── Dockerfile
│   │   └── alembic/            # Database migrations
│   └── alembic.ini
├── frontend/                   # React + Vite + TypeScript
│   ├── src/
│   ├── package.json
│   ├── Dockerfile
│   └── tsconfig.json
├── ops/                        # Observability configs (Prometheus, Grafana, Alertmanager)
└── docs/                       # Documentation
```

---

## Quick Start (Docker Compose — Recommended)

### 1. Clone & Enter Repo

```powershell
# In VS Code Terminal (Ctrl+`)
cd C:\Users\Appex\Documents\Default Project\CampusPilot
```

### 2. Configure Environment

```powershell
# Copy the example env file
cp .env.example .env

# (Optional) IMAP/Email config
cp .env.imap.example .env.imap
```

Edit `.env` and fill in:
- `SECRET_KEY` — generate with `python -c "import secrets; print(secrets.token_hex(32))"`
- `TELEMETRY_PEPPER` — generate with `python -c "import secrets; print(secrets.token_hex(32))"`
- `SMTP_*` — your email credentials (optional, for password reset)
- `ALERT_TELEGRAM_*` — Telegram bot for alerts (optional)

### 3. Start the Stack

```powershell
# From repo root (where docker-compose.yml lives)
docker compose --profile lite up -d --build
```

This starts:
- **postgres** (port 5432)
- **backend** (port 8002 → container 8001)
- **frontend** (port 5174 → container 80)
- **prometheus** (port 9090)
- **node-exporter** (port 9100)
- **alertmanager** (port 9093)
- **rollup** (background worker)

### 4. Verify

| Service | URL | Health Check |
|---------|-----|--------------|
| Frontend | <http://localhost:5174> | Loads React app |
| Backend API | <http://localhost:8002/health> | `{"status":"ok"}` |
| API Docs | <http://localhost:8002/docs> | Swagger UI |
| Prometheus | <http://localhost:9090> | Targets UP |
| Alertmanager | <http://localhost:9093> | UI loads |

---

## Manual Backend Development (Without Docker)

### 1. Enter Backend Directory

```powershell
cd backend\backend
```

### 2. Create Virtual Environment (Python 3.10)

```powershell
# Create venv
python -m venv .venv

# Activate (VS Code Terminal)
.\.venv\Scripts\Activate.ps1

# Upgrade pip
python -m pip install --upgrade pip
```

### 3. Install Dependencies

```powershell
# Install runtime deps
pip install -r ..\requirements.txt

# Install dev deps (if you have requirements-dev.txt)
pip install -r ..\requirements-dev.txt 2>$null
```

### 4. Configure Local .env

```powershell
# Copy and edit
cp ..\.env.example .env
# Edit .env with your local DATABASE_URL:
# DATABASE_URL=postgresql+psycopg://campuspilot:campuspilot@localhost:5432/campuspilot
```

### 5. Run Migrations

```powershell
# From backend/backend/
python -m alembic -c alembic.ini upgrade head
```

### 6. Run Backend

```powershell
# From backend/backend/
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8001 --reload
```

API available at: <http://localhost:8001> | Docs: <http://localhost:8001/docs>

### 7. Run Tests

```powershell
# From backend/backend/
python -m pytest tests/ -v --tb=short
```

---

## Frontend Development

### 1. Enter Frontend Directory

```powershell
cd frontend
```

### 2. Install Dependencies

```powershell
npm install
```

### 3. Run Dev Server

```powershell
npm run dev
```

Frontend available at: <http://localhost:5173> (proxied to backend at 8001)

### 3. Build for Production

```powershell
npm run build
# Output in dist/
```

### 4. Run Tests

```powershell
npm test
```

---

## VS Code Terminal Tips

### Use Integrated Terminal (Recommended)

1. Open repo in VS Code: `File → Open Folder → C:\Users\Appex\Documents\Default Project\CampusPilot`
2. Open terminal: **Terminal → New Terminal** (or `Ctrl+``)
3. **Split terminal** for multiple shells: Click the split icon (⊞) or `Ctrl+Shift+5`

### Recommended Terminal Layout

| Pane | Purpose | Directory |
|------|---------|-----------|
| 1 | Backend server | `backend\backend` |
| 2 | Frontend dev server | `frontend` |
| 3 | Docker / DB / Tests | Repo root |

### PowerShell Profile for Aliases (Optional)

Add to `$PROFILE` (run `notepad $PROFILE`):

```powershell
# CampusPilot aliases
function cdb { cd "C:\Users\Appex\Documents\Default Project\CampusPilot" }
function cdb-b { cdb; cd backend\backend }
function cdb-f { cdb; cd frontend }
function cdb-t { cdb; python -m pytest backend\backend\tests\ -v }
function cdb-m { cdb; python -m alembic -c backend\alembic.ini upgrade head }
```

Reload: `. $PROFILE`

---

## Database Management

### Run Migrations (Any Environment)

```powershell
# From backend/backend/
python -m alembic -c alembic.ini upgrade head
```

### Create New Migration

```powershell
python -m alembic -c alembic.ini revision --autogenerate -m "your message"
```

### Rollback

```powershell
# One step
python -m alembic -c alembic.ini downgrade -1

# To base
python -m alembic -c alembic.ini downgrade base
```

### Direct PostgreSQL Access

```powershell
# From host (if Docker published port 5432)
psql -h localhost -U campuspilot -d campuspilot
# Password: campuspilot (from .env)
```

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `ModuleNotFoundError: No module named 'core'` | Ensure `PYTHONPATH=/app/backend` or run from `backend/backend` with venv active |
| `psycopg.OperationalError: connection refused` | PostgreSQL not ready; check `docker logs campuspilot-postgres-1` |
| `Temporary failure in name resolution` | DNS issue in Docker network; retry logic in `create_engine_with_retry` handles this |
| `port 5432 already allocated` | Kill local postgres: `taskkill /PID <pid> /F` (find with `netstat -ano \| findstr :5432`) |
| `port 8002 already allocated` | `taskkill /PID <pid> /F` (find with `netstat -ano \| findstr :8002`) |
| Frontend build fails | `cd frontend && rm -rf node_modules package-lock.json && npm install` |
| Python 3.11+ errors | Ensure `python --version` shows 3.10.x; recreate venv with `python3.10 -m venv .venv` |

---

## Port Reference

| Service | Host Port | Container Port | Notes |
|---------|-----------|----------------|-------|
| PostgreSQL | 5432 | 5432 | Published for host access |
| Backend API | 8002 | 8001 | Host 8002 → Container 8001 |
| Frontend | 5174 | 80 | Vite dev server on 5173 |
| Prometheus | 9090 | 9090 | |
| Alertmanager | 9093 | 9093 | |
| Node Exporter | 9100 | 9100 | |

---

## Environment Variables Reference (`.env`)

```bash
# Required
SECRET_KEY=your-32-char-secret
TELEMETRY_PEPPER=your-32-char-pepper
DATABASE_URL=postgresql+psycopg://campuspilot:campuspilot@localhost:5432/campuspilot

# Optional (Email)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your@email.com
SMTP_PASSWORD=your-app-password
EMAIL_FROM=noreply@yourdomain.com

# Optional (Alerting)
ALERT_TELEGRAM_BOT_TOKEN=...
ALERT_TELEGRAM_CHAT_ID=...
ALERT_WEBHOOK_URL=...

# Feature flags
TELEMETRY_ENABLED=false
METRICS_ENABLED=true
ROLLUP_INLINE=true
SCAN_ENABLED=false
```

---

## Useful Commands Cheatsheet

```powershell
# Full stack (Docker)
docker compose --profile lite up -d --build
docker compose --profile lite down -v

# Backend only
cd backend\backend; .\.venv\Scripts\Activate.ps1; python -m uvicorn backend.main:app --reload

# Frontend only
cd frontend; npm run dev

# Tests
cd backend\backend; python -m pytest tests/ -v
cd frontend; npm test

# Migrations
cd backend\backend; python -m alembic -c alembic.ini upgrade head

# Logs
docker logs campuspilot-backend-1 -f
docker logs campuspilot-postgres-1 -f

# Clean slate
docker compose --profile lite down -v
docker system prune -f
```

---

## Notes

- **Always run commands from the correct directory** — backend commands from `backend/backend`, frontend from `frontend`, docker from repo root.
- **VS Code terminal** preserves environment across splits — use splits for parallel processes.
- **Python 3.10 is mandatory** — the `as const` assertions and some typing features behave differently in 3.11+.
- **Docker Desktop on Windows** can be flaky — if `docker compose` fails to connect, restart Docker Desktop and wait 60s.

---

*Generated for CampusPilot v0.1.0 — see `docs/ROADMAP.md` for project roadmap.*