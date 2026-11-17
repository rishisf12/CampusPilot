# Phase 0 Report — Foundation, Docker & Walking Skeleton

**Status:** Scaffold complete; live boot verification blocked by environment (no Docker daemon, no npm registry access).

## What was created

| Path | Purpose |
|---|---|
| `docker-compose.yml` | db (postgres:16), redis, mailserver (greenmail/standalone), backend, worker, frontend (nginx); healthchecks; volumes; `depends_on: condition: service_healthy` |
| `.env.example` / `.env` | All env vars (no secrets in git) |
| `Makefile` | `up`, `down`, `logs`, `ps`, `test`, `lint`, `seed`, `clean` |
| `backend/Dockerfile` | python:3.12-slim, non-root user, alembic upgrade head + uvicorn |
| `backend/pyproject.toml` | Pinned deps (fastapi, sqlmodel, asyncpg, aiosmtplib, aioimaplib, nh3, selectolax, redis, arq, passlib, python-jose, cryptography, …) + dev (pytest, httpx, ruff, mypy) |
| `backend/alembic.ini` + `alembic/env.py` + `alembic/versions/` | Alembic async setup, sync URL for env.py |
| `backend/app/main.py` | FastAPI app, `/`, `/api/v1/health`, `/api/v1/health/ready`, CORS, lifespan init_db |
| `backend/app/core/config.py` | pydantic-settings, all config from env |
| `backend/app/core/logging.py` | structured logging config |
| `backend/app/db/session.py` | async engine (asyncpg), session factory, init_db |
| `backend/app/db/base.py` | SQLModel Base metadata |
| `backend/app/api/v1/health.py` | health + ready probes |
| `frontend/Dockerfile` + `nginx.conf` | Vite build → nginx, `/api` + `/ws` proxy, security headers |
| `frontend/package.json` | React 18, TS, Vite, Tailwind v4, shadcn/Radix, TanStack Query, Zustand, React Router, TipTap-adjacent, cmdk, react-i18next, vite-plugin-pwa; vitest + RTL + eslint + tsc |
| `frontend/vite.config.ts` | react + PWA plugin, `/api` + `/ws` dev proxy |
| `frontend/postcss.config.js`, `tsconfig.json`, `index.html`, `src/index.css` (`@import "tailwindcss"`) | Tailwind v4 inline setup |
| `frontend/src/main.tsx`, `App.tsx`, `pages/Health.tsx`, `lib/api.ts` | App shell, router, query client, health page calling `/api/v1/health` |
| `docs/PLAN.md` | Expanded phase checklist + pinned versions |
| `docs/BUGLOG.md` | Empty bug log template |
| `docs/phases/` | Phase report directory |
| `README.md` | Quick start |

## Verification performed (static)

- `docker compose config --quiet` → **valid** (only warnings: unset env vars when `.env` not loaded; with `.env` present these resolve)
- All file paths present (see glob above)

## Verification NOT possible in this environment

| Gate | Blocker |
|---|---|
| `docker compose up -d --build` → all healthy < 90 s | Docker daemon unavailable (`npipe:////./pipe/dockerDesktopLinuxEngine` not found) |
| `curl /api/v1/health`, `/ready` | Depends on running stack |
| Alembic `upgrade head` / `downgrade base` | Depends on running Postgres |
| Frontend `npm install` / `npm run build` / `tsc --noEmit` | npm registry access timed out (10 min) |
| GreenMail reachability `nc -z mailserver 3143` | Depends on running stack |

## Bugs found

None (no live system to test yet).

## Next

Move to an environment with Docker daemon + network access and run:

```bash
cd posthaven
docker compose up -d --build
# wait for healthy
curl http://localhost:8000/api/v1/health/ready
curl http://localhost:5173/health
docker compose exec backend alembic upgrade head
docker compose exec backend alembic downgrade base
docker compose exec backend alembic upgrade head
```

Then proceed to Phase 1 (Auth, Users & Multi-Tenancy).
