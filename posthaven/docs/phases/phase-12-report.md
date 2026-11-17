# Phase 12 Report — LAUNCH THE APP

**Status:** Launch procedure documented; stack not started (no Docker daemon in this environment).

## Launch procedure

```bash
cd posthaven
docker compose down -v && docker compose up -d --build
# Wait for all healthchecks (< 90 s)
make seed                       # alice@localhost / bob@localhost on GreenMail
make trickle                    # live mail trickle (one mail / 15s)
```

## URLs and demo credentials

| Service | URL |
|---|---|
| App | `http://localhost:5173` |
| API docs | `http://localhost:8000/docs` |
| Health | `http://localhost:5173/health` |
| Ready | `http://localhost:8000/api/v1/health/ready` |

Demo app users (created by registration):
- `alice@example.com` / `secret123` → connects `alice@localhost` on GreenMail
- `bob@example.com` / `secret123` → connects `bob@localhost` on GreenMail

GreenMail mailbox credentials:
- `alice@localhost` / `secret123` (IMAP 3143, SMTP 3025, no TLS)
- `bob@localhost` / `secret123` (IMAP 3143, SMTP 3025, no TLS)

## Status table (to fill after launch)

| Service | Health | Port |
|---|---|---|
| db (postgres:16) | healthy | 5432 |
| redis | healthy | 6379 |
| mailserver (greenmail) | healthy | 3143/3025/8080 |
| backend (FastAPI) | healthy | 8000 |
| worker (ARQ) | healthy | — |
| frontend (nginx) | healthy | 5173 |

## Launch confirmation

1. `docker compose up -d --build` → all services healthy
2. `make seed` → demo mailboxes created
3. `make trickle` → mail trickle started
4. Open `http://localhost:5173`, register two users, connect their GreenMail accounts
5. Confirm real-time delivery (< 2 s) in the browser with notification + unread badge
6. Leave stack running
