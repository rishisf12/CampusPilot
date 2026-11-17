# PostHaven Architecture

## Overview

PostHaven is a multi-user, real-time web mail client. Users register, connect their own IMAP/SMTP accounts, and read/send mail in real time.

## Data flow

```
Browser ──HTTPS──> nginx(frontend) ──/api──> FastAPI ──> PostgreSQL (SQLModel)
   ▲                         └──/ws──> FastAPI WS ◄── Redis pub/sub ◄── Worker
   │                                                         ▲               │
   └──────── real-time events ◄──────────────────────────────┘      IMAP IDLE per account
                                                                    (GreenMail / real IMAP)
                                                              SMTP send ──► (GreenMail / real SMTP)
```

## Components

| Component | Responsibility |
|---|---|
| `db` (Postgres 16) | Source of truth: users, accounts, messages, folders, threads, labels, rules, snooze, drafts, scheduled sends |
| `redis` | Pub/sub fan-out for WebSocket events, rate-limit counters, ARQ job queue |
| `mailserver` (GreenMail) | Mock SMTP/IMAP/POP3 for dev/test (no real mail leakage) |
| `backend` (FastAPI) | REST API `/api/v1`, WebSocket `/ws`, auth, sync orchestration |
| `worker` (ARQ) | Background jobs: send_email, wake_snooze, run_rule, send_reminder |
| `frontend` (nginx + Vite build) | SPA served by nginx, proxies `/api` + `/ws` to backend |

## Sync model

PostgreSQL is a cache/index of IMAP, not the source of truth. Each folder stores `uidvalidity`, `uidnext`, `highestmodseq`. Messages are upserted keyed by `(account_id, folder_id, uid)`. If `uidvalidity` changes, the folder resyncs.

## Real-time contract

WebSocket `/ws` (auth via httpOnly `access_token` cookie):
- Server → client: `{type, account_id, payload, ts}` — `message.new`, `message.updated`, `message.deleted`, `folder.counts`, `sync.status`, `send.status`, `snooze.woke`, `reminder.due`
- Client → server: `ping`, `subscribe(account_ids)`
- Heartbeat 25s; catch-up via `GET /sync/since?cursor=`

## Security

- Argon2 password hashing; JWT 15-min access + rotating refresh tokens
- Mail credentials encrypted at rest (Fernet, key from `ENCRYPTION_KEY`)
- SSRF guard on connection tests (`ALLOW_PRIVATE_MAIL_HOSTS`)
- HTML email sanitized (nh3 allow-list), remote images blocked by default
- CSP, X-Content-Type-Options, Referrer-Policy, X-Frame-Options headers
- Every data endpoint tenant-scoped by `user_id`

## Environment variables

See `.env.example`. Key vars: `DATABASE_URL`, `REDIS_URL`, `SECRET_KEY`, `ENCRYPTION_KEY`, `ALLOW_PRIVATE_MAIL_HOSTS`, `FRONTEND_ORIGIN`, `GREENMAIL_HOST`.
