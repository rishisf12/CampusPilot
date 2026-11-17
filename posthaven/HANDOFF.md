# PostHaven — Handoff

## Done
- Phases 0–12 code complete; `docker compose up -d --build` brings up all services (healthy)
- Live verification 2026-11-04 — full golden path works: register/login (JSON bodies, httpOnly
  cookies) → `/mail` shell renders, zero console errors; `/ws` reachable; GreenMail up
- 9 bugs found & fixed (see docs/BUGLOG.md PH-001…PH-009):
  - Frontend: blank page (React Router v6 pathless `<Route>`); double `/api/api/v1` fetch base;
    `MessageList` used undeclared `loading`; labels not linked to inputs; SW stale cache
  - Backend: SQLAlchemy `AsyncSession` vs SQLModel `.exec()`; empty models registry (mappers not
    configured); relationship join columns without `ForeignKey` + `back_populates` mismatches;
    naive vs tz-aware datetimes (migrations use timestamptz); login/change-password/create-scheduled
    expected query params while frontend sends JSON; WS mounted at `/api/v1/ws` instead of `/ws`
- Docs: BUGLOG.md updated with live-verification findings
- HANDOFF secret note: dev `.env` secrets must be rotated for production

## Decisions
- Separate project at `posthaven/`; stack per prompt; GreenMail dev server; ARQ worker;
  httpOnly JWT cookies; Fernet credential encryption; SSRF guard on mail hosts
- WS endpoint lives at `/ws` (outside `/api/v1`) to match nginx proxy and frontend

## Next step
1. Hard-refresh http://localhost:5173 if UI looks stale (PWA SW) — or unregister SW in DevTools
2. Seed GreenMail (`make seed`), `make trickle`; add accounts (mailserver:3143/3025, no TLS,
   pass `secret123`); send mail and verify real-time delivery
3. Re-verify & refresh phase reports (they say "blocked by environment" — no longer true)
4. Commit per `phase-XX:` convention — nothing committed yet
