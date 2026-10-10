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
├── docker-compose.yml          # The only compose file (at repo root)
├── .env.example                # Copy to .env and fill in secrets
├── .env.imap.example           # IMAP-specific env vars
├── .dockerignore               # Keeps node_modules, dist, .env out of images
├── .gitattributes              # Pins .husky/** to LF (hooks are run by sh)
├── backend/
│   ├── alembic.ini             # Migrations run from HERE
│   ├── alembic/                # Database migrations
│   ├── requirements.txt        # Python deps
│   ├── Dockerfile              # Listens on container port 8001
│   └── backend/                # FastAPI package — server & tests run from HERE
│       ├── core/               # Database, config, security
│       ├── features/           # Feature modules (auth, monitoring, etc.)
│       ├── main.py             # FastAPI entry point
│       └── tests/
├── frontend/                   # React + Vite + TypeScript
│   ├── src/                    # .tsx only — the .jsx migration is complete
│   ├── vite.config.ts          # Dev proxy config (keep only this one file)
│   ├── nginx.conf              # Container proxy (no per-router list)
│   ├── package.json
│   ├── Dockerfile              # Serves on container port 80
│   └── tsconfig.json
├── mcp-crash-monitor/          # Read-only MCP server over monitoring tables
│   └── src/index.ts
├── ops/                        # Observability configs (Prometheus, Grafana, Alertmanager)
└── docs/                       # Documentation
```

> **There is exactly one `vite.config` and one `docker-compose.yml`.** Both
> used to have a stale duplicate that shadowed the real one. If you add a second
> copy, check which file the tooling actually reads first.

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

> **Two directories, two purposes.** `backend/` holds `alembic.ini` and
> `requirements.txt`, so migrations run from there. `backend/backend/` holds
> `main.py` and the flat-import packages (`core`, `features`), so the server and
> the tests run from there. The app uses flat imports (`from core.config import
> ...`), which is why it must be started inside the package directory rather
> than as `backend.main:app`.

### 1. Create Virtual Environment (Python 3.10)

```powershell
cd backend\backend
python -m venv .venv

# Activate (VS Code Terminal)
.\.venv\Scripts\Activate.ps1

# Upgrade pip
python -m pip install --upgrade pip
```

### 2. Install Dependencies

```powershell
# requirements.txt lives one level up, next to alembic.ini
pip install -r ..\requirements.txt
```

### 3. Configure Local .env

```powershell
# Copy and edit
cp ..\.env.example .env
# Edit .env with your local DATABASE_URL:
# DATABASE_URL=postgresql+psycopg://campuspilot:campuspilot@localhost:5432/campuspilot
```

### 4. Run Migrations

```powershell
# From backend/  -- NOT backend/backend/, which has no alembic.ini
cd backend
python -m alembic -c alembic.ini upgrade head
```

Check where you are with `python -m alembic -c alembic.ini current`; it should
print the current revision, not `FAILED: No config file 'alembic.ini' found`.

### 5. Run Backend

```powershell
# From backend/backend/
python -m uvicorn main:app --port 8000 --reload
```

API available at: <http://127.0.0.1:8000> | Docs: <http://127.0.0.1:8000/docs>

> **Port 8000 is what the Vite dev proxy expects.** Keep it in step with
> `VITE_DEV_BACKEND` in `frontend/vite.config.ts`. If you need a different
> port, change the proxy target rather than only the server flag, or every
> request through the dev server fails.

### 6. Run Tests

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

Frontend available at: <http://localhost:5173> (proxied to the backend at 8000)

### 4. Build for Production

```powershell
npm run build
# Output in dist/
```

### 5. Run Tests

```powershell
npm test
```

### Pointing the Dev Server at a Different Backend

The proxy target defaults to `http://127.0.0.1:8000` and can be overridden:

```powershell
# e.g. when the backend runs in Docker on 8002
$env:VITE_DEV_BACKEND = "http://127.0.0.1:8002"
npm run dev
```

> **Use the IP literal, not `localhost`.** `localhost` resolves to `::1` first
> on Windows, and uvicorn binds IPv4-only, so the proxy gets `ECONNREFUSED`
> and every endpoint returns a 500 with an empty body even though the backend
> is healthy.

### Only One `vite.config` May Exist

Vite resolves `vite.config.js` **before** `vite.config.ts`. If both are
present the `.js` wins and the file you are editing is ignored with no warning
anywhere — the dev server keeps proxying to whatever the stale file says.

There is a test that fails if a shadow reappears
(`backend/backend/tests/test_proxy_coverage.py`), and it reads the `.ts` file,
so it validates the config that actually runs.

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
| `ModuleNotFoundError: No module named 'core'` | Wrong directory. Run the server from `backend/backend` (flat imports), or set `PYTHONPATH=/app/backend` in Docker |
| `FAILED: No config file 'alembic.ini' found` | Running migrations from `backend/backend`. `alembic.ini` is in `backend/` — `cd backend` first |
| `ModuleNotFoundError: No module named 'backend'` | Running `uvicorn backend.main:app` from `backend/backend`. Use `uvicorn main:app` there |
| Every request through :5173 returns **500 with an empty body** | Proxy cannot reach the backend. Check `VITE_DEV_BACKEND` in `frontend/vite.config.ts`, and that no stale `vite.config.js` is shadowing the `.ts`. `localhost` resolves to `::1` and uvicorn is IPv4-only — use `127.0.0.1` |
| `Backend offline` banner in the UI | The dev proxy cannot reach the backend; see the row above. Confirm `curl http://127.0.0.1:8000/health` returns `{"status":"ok"}` |
| `psycopg.OperationalError: connection refused` | PostgreSQL not ready; check `docker logs campuspilot-postgres-1`. `create_engine_with_retry` retries with backoff at startup |
| `Temporary failure in name resolution` | DNS issue in Docker network; retry logic in `create_engine_with_retry` handles this |
| `port 5432 already allocated` | Kill local postgres: `taskkill /PID <pid> /F` (find with `netstat -ano \| findstr :5432`) |
| `port 8002 already allocated` | `taskkill /PID <pid> /F` (find with `netstat -ano \| findstr :8002`) |
| Frontend build fails | `cd frontend && rm -rf node_modules package-lock.json && npm install` |
| Python 3.11+ errors | Ensure `python --version` shows 3.10.x; recreate venv with `python3.10 -m venv .venv` |

---

## Port Reference

There are three different backend ports, which is the single most confusing
thing about this project:

| Context | Port | Where it comes from |
|---------|------|--------------------|
| **Local dev** (no Docker) | **8000** | What you pass to uvicorn, and what the Vite proxy targets |
| **Docker** (host side) | **8002** | `ports: "8002:8001"` in `docker-compose.yml` |
| **Docker** (container side) | **8001** | `EXPOSE`/`CMD` in `backend/Dockerfile`; nginx proxies to `http://backend:8001` |

So the Vite proxy must point at **8000** locally, or **8002** if the backend is
in Docker. It never points at 8001 — that port only exists inside the compose
network.

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

# Backend only (from backend/backend, venv activated)
.\.venv\Scripts\Activate.ps1; python -m uvicorn main:app --port 8000 --reload

# Frontend only
cd frontend; npm run dev

# Tests
cd backend\backend; python -m pytest tests/ -v
cd frontend; npm test

# Migrations (from backend/, NOT backend/backend/)
cd backend; python -m alembic -c alembic.ini upgrade head

# Lint
python -m ruff check backend/backend/
cd frontend; npm run lint

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

## Optional: Crash-Monitor MCP Server

`mcp-crash-monitor/` is a read-only MCP server over the app's own monitoring
tables, so crash and telemetry analysis needs no third-party hosted service.
It connects with the same PostgreSQL you already run.

```powershell
cd mcp-crash-monitor
npm install
npm run build     # tsc — dist/ is gitignored, so a fresh clone must build
npm start
```

Configuration lives in `.env` (copy from `.env.example`):

```bash
DATABASE_URL=postgresql://campuspilot:campuspilot@localhost:5432/campuspilot
```

In a shared environment point `DATABASE_URL` at a `SELECT`-only role (for
example `monitoring_ro`, created by migration
`0c60d501467d`) rather than the application role.

It is registered in `docs/observability/opencode.json` as the `crash-monitor`
MCP server, and runs `node dist/index.js` from `./mcp-crash-monitor`.

---

*Generated for CampusPilot v0.1.0 — see `docs/ROADMAP.md` for project roadmap.*