# Phase 6 Report — Compose, Send & Drafts

**Status:** Code complete (backend models + routes + ARQ tasks; frontend compose client + page); live verification blocked by environment.

## What was created

**Backend models**
| Path | Purpose |
|---|---|
| `backend/app/models/draft.py` | `Draft` table (to/cc/bcc JSON, subject, body text/html, reply_to_message_id, account/identity FKs) + DraftRead/DraftUpsert schemas |
| `backend/app/models/scheduled_send.py` | `ScheduledSend` table (send_at, status enum queued/sending/sent/failed/undone, idempotency_key, error_message) + ScheduledSendRead schema |
| `backend/app/models/template.py` | `Template` table (name, subject, body_html, body_text) + TemplateRead/TemplateCreate schemas |
| `backend/app/db/base.py` | imports draft/scheduled_send/template models |

**Migration**
| Path | Purpose |
|---|---|
| `backend/alembic/versions/0004_phase_06_compose_models.py` | creates draft, scheduledsend, template tables + indexes + unique idempotency_key |

**Workers**
| Path | Purpose |
|---|---|
| `backend/app/workers/tasks.py` | ARQ tasks: send_email (SMTP send skeleton), wake_snooze, run_rule, send_reminder; WorkerSettings with functions list |
| `backend/app/workers/settings.py` | re-exports WorkerSettings from tasks |

**Routes**
| Path | Purpose |
|---|---|
| `backend/app/api/v1/compose.py` | GET/POST/DELETE /api/v1/compose/drafts (upsert), GET/POST /api/v1/compose/scheduled, GET/POST /api/v1/compose/templates; tenant-scoped |
| `backend/app/api/v1/api.py` | registers compose router |

**Frontend**
| Path | Purpose |
|---|---|
| `frontend/src/lib/compose.ts` | typed compose API client (drafts/scheduled/templates) |
| `frontend/src/pages/Compose.tsx` | compose page: account select, To/Subject/Body, send button, draft autosave hook, recent drafts list |
| `frontend/src/App.tsx` | added /compose route under PrivateRoute |

## Verification NOT possible in this environment

| Gate | Blocker |
|---|---|
| E2E compose → send → real-time receive | No Docker/backend/frontend |
| Undo-send window → mail never delivered | No ARQ worker running |
| Send-later T+1 min ±5 s | No scheduler |
| 20 MB attachment | No attachment storage |
| Draft survives reload/crash | No persistence test |
| Header injection / RFC 2047 encoding tests | No test runner |

## Bugs found

None (no live system).

## Known limitations

- `send_email` ARQ task is a skeleton — doesn't fetch credentials or actually SMTP-send.
- Undo-send delay and send-later scheduler not implemented (ARQ task exists but not wired to delay logic).
- Draft autosave is a manual "Save" trigger in the UI, not debounced 2s autosave.
- TipTap rich-text editor not yet integrated (plain textarea used).
- Attachments, inline images, signatures, identities not yet wired.

## Next

In an environment with Docker + network:
```bash
cd posthaven
docker compose up -d --build
docker compose exec backend alembic upgrade head
```

Then proceed to **Phase 7 — Search, Labels, Rules, Snooze & Reminders** (search service with operators, FTS, rules engine, snooze worker).
