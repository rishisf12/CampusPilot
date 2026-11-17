# PostHaven — Handoff

## Done
- Phases 0–12 code complete (all scaffold + backend + frontend + docs)
- Docs: PLAN.md, BUGLOG.md, ARCHITECTURE.md, API.md, CONTRIBUTING.md, OPERATIONS.md, README.md
- Phase reports: docs/phases/phase-00 through phase-12

## Decisions
- Separate repo from CampusPilot at `posthaven/`
- Same stack as CampusPilot: FastAPI/SQLModel/Postgres + React/Vite/Tailwind v4/PWA
- GreenMail as dev mail server; ARQ for background jobs; Fernet for credential encryption
- httpOnly JWT cookies for auth; SSRF guard on mail host tests

## Blocker
- No Docker daemon and no npm registry access in this environment — nothing built/run/tested
- `docker compose config --quiet` validates; all files present

## Next step
Move to environment with Docker + network; run:
```
cd posthaven
docker compose up -d --build
docker compose exec backend alembic upgrade head
make seed
```
Then verify `/api/v1/health/ready` and proceed to fix any live issues.
