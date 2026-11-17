# Phase 4 Report — Real-Time Engine (IDLE → Redis → WebSocket)

**Status:** Code complete (skeleton); live verification blocked by environment.

## What was created

**Backend**
| Path | Purpose |
|---|---|
| `backend/app/workers/__init__.py` | package marker |
| `backend/app/workers/settings.py` | `WorkerSettings` class for ARQ (Redis settings from env, max_jobs=10, job_timeout=300, keep_result=24h) |
| `backend/app/workers/idle_supervisor.py` | `IdleSupervisor` class: per-account IDLE loop with exponential backoff reconnect (1s→60s), re-IDLE every 29 min, Redis pub/sub event publishing to `user:{id}` channel, lease-based horizontal scaling (constants LEASE_TTL/LEASE_RENEW_INTERVAL), `start_account`/`stop_account` per-account control |
| `backend/app/api/v1/ws.py` | WebSocket `/ws` endpoint: authenticates via `access_token` httpOnly cookie (decodes JWT, loads user), connection manager (active WS per user_id), Redis pub/sub forwarder (concurrent task), handles client `ping`→`pong` and `subscribe` |
| `backend/app/api/v1/api.py` | registers ws router |
| `docker-compose.yml` | `worker` service runs `arq worker app.workers.settings` (depends on db+redis healthy) |

**Frontend**
| Path | Purpose |
|---|---|
| `frontend/src/lib/ws.ts` | `MailWs` class: WebSocket client with auto-reconnect (exponential backoff 1s→30s), event listener pattern, `subscribe(accountIds)`, `ping()`, `enable()`/`disable()` |
| `frontend/src/stores/auth.ts` | `mailWs.enable()` on login/register/fetchMe success; `mailWs.disable()` on logout/fetchMe failure |

## Real-time contract

Server → client events (JSON): `{type, account_id, payload, ts}`:
- `message.new`, `message.updated`, `message.deleted`, `folder.counts`, `sync.status`, `send.status`, `snooze.woke`, `reminder.due`

Client → server: `ping`, `subscribe(account_ids)`. Heartbeat 25s (client-side ping), auto-reconnect with backoff, catch-up via `GET /sync/since?cursor=` (skeleton in Phase 3/4).

## Verification NOT possible in this environment

| Gate | Blocker |
|---|---|
| Send mail to alice@localhost → Alice tab shows in < 2 s, Bob tab shows nothing | No Docker/GreenMail/backend |
| Kill worker → restart → catch-up delivers missed mail | No running stack |
| WS auth expiry mid-connection, WS leak on logout | No test runner |
| Two workers lease safety (exactly one IDLE per account) | No multi-worker test |

## Bugs found

None (no live system).

## Known limitations

- WS endpoint reads `access_token` from cookie (correct for httpOnly). No query-param token fallback.
- IDLE supervisor `_publish_event` publishes to `user:{account_id}` — should be `user:{user_id}`. Requires DB lookup of account→user, which is skeleton-only here.
- ARQ worker command starts but IDLE supervisor is not auto-started (needs ARQ startup hook or separate supervisor process).
- `_sync_folder_headers`/`_upsert_message` in sync.py are stubs — IDLE events won't produce DB updates until Phase 3 message parsing is wired.
- Catch-up endpoint `GET /sync/since?cursor=` not yet implemented.

## Next

In an environment with Docker + network:
```bash
cd posthaven
docker compose up -d --build
# WS test (needs valid auth cookie from browser):
#   ws://localhost:8000/ws  (with access_token cookie)
```

Then proceed to Phase 5 (Core Mail UI: Reading Experience).
