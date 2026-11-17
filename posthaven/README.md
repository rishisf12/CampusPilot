# PostHaven

Multi-user, real-time web mail client. PostgreSQL + SQLModel + FastAPI + React + Tailwind v4.

## Quick start

```bash
cp .env.example .env   # edit if needed
docker compose up -d --build   # builds & starts db, redis, mailserver, backend, worker, frontend
```

Wait for all services to be healthy, then:

- App: `http://localhost:5173`
- API docs: `http://localhost:8000/docs`
- Health: `http://localhost:5173/health`
- Ready: `http://localhost:8000/api/v1/health/ready`

Stop: `docker compose down`  
Wipe data: `docker compose down -v`

## Seed demo mailboxes

```bash
make seed   # creates alice@localhost / bob@localhost on GreenMail (password: secret123)
```

## Phases

Work is tracked in `docs/PLAN.md`. Phase reports live in `docs/phases/`. Bug log: `docs/BUGLOG.md`.

## Feature matrix

| Feature | Status | Inspired by |
|---|---|---|
| Register/login, JWT httpOnly cookies | ✅ Phase 1 | Roundcube, SnappyMail |
| Multiple IMAP/SMTP accounts, encrypted creds | ✅ Phase 2 | Roundcube, Zero |
| SSRF guard, capability detection | ✅ Phase 2 | Zero |
| IMAP IDLE → Redis → WebSocket real-time | ✅ Phase 4 | Zero, Mailspring |
| Three-pane layout, folders, virtualized list | ✅ Phase 5 | Roundcube, SnappyMail |
| Sanitized HTML, remote images blocked | ✅ Phase 5 | SnappyMail, Roundcube |
| Keyboard shortcuts + command palette | ✅ Phase 5 | Mailspring, SnappyMail |
| Light/dark/system theme | ✅ Phase 5 | Mailspring, Zero |
| Drafts autosave, compose | ✅ Phase 6 | Mailspring |
| Scheduled send / undo-send (skeleton) | 🚧 Phase 6 | Mailspring |
| Search (operators + FTS) | ✅ Phase 7 | Mailspring, Roundcube |
| Labels, rules, snooze | ✅ Phase 7 | Mailspring, SnappyMail |
| Contacts, groups, autocomplete | ✅ Phase 8 | Roundcube |
| Settings, admin | ✅ Phase 9 | Zero |
| PWA (manifest + SW) | 🚧 Phase 9 | Zero |
| i18n (en/hi/es/fr) | 🚧 Phase 9 | Roundcube |
| Contacts vCard/CSV import/export | 🚧 Phase 8 | Roundcube |
| Security hardening (middleware) | ✅ Phase 10 | SnappyMail |
| E2E golden-path tests | ✅ Phase 11 | — |

✅ = implemented · 🚧 = skeleton/partial

## Architecture

See `docs/ARCHITECTURE.md`. API reference: `docs/API.md`.

## Security

Mail credentials are encrypted at rest. No read-receipt or link-tracking pixel injection. No third-party analytics.
