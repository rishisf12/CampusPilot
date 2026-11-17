# Contributing to PostHaven

## Setup

```bash
git clone <repo>
cd posthaven
cp .env.example .env
docker compose up -d --build
```

## Phases

Work is tracked in `docs/PLAN.md` (phase checklist) and `docs/BUGLOG.md` (bug log). Each phase ends with a gate:
1. Verification (tests pass)
2. Bug identification (deliberate bug hunt)
3. Fix + regression tests
4. Write `docs/phases/phase-XX-report.md`
5. Commit `phase-XX: <summary>`

## Code style

- Backend: `ruff check`, `ruff format`, `mypy --strict`
- Frontend: `eslint`, `tsc --noEmit`
- Commit messages: imperative mood, explain why not what

## Testing

- Backend: `pytest` (integration tests with real Postgres/Redis/GreenMail)
- Frontend: `vitest` + React Testing Library
- E2E: `playwright` (golden paths)

## Security

Never commit `.env` or secrets. Mail credentials are encrypted at rest; report security issues privately.
