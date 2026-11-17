# Phase 3 Report — Mailbox Sync Engine (Folders & Messages)

**Status:** Code complete (sync service skeleton); live verification blocked by environment.

## What was created

**Backend models**
| Path | Purpose |
|---|---|
| `backend/app/models/folder.py` | `Folder` table (name, delimiter, parent, special_use, subscribed, uidvalidity, uidnext, highestmodseq, message_count, unread_count, synced) + schemas |
| `backend/app/models/message.py` | `Message` table (uid, message_id, in_reply_to, references, from/to/cc/bcc JSON, subject, snippet, body_text, body_html, search_vector, flags, size, has_attachments, internal_date, received_at) + GIN index on search_vector, unique (account_id, folder_id, uid) + schemas |
| `backend/app/models/thread.py` | `Thread` table (subject, message_count, unread_count, last_message_at) + schemas |
| `backend/app/models/attachment.py` | `Attachment` table (filename, mime_type, size, content_id, is_inline, storage_path) + schemas |
| `backend/app/models/label.py` | `Label` + `MessageLabel` (many-to-many) tables + schemas |
| `backend/app/db/base.py` | imports all new models |
| `backend/app/models/user.py` | added `threads` relationship |

**Migration**
| Path | Purpose |
|---|---|
| `backend/alembic/versions/0003_phase_03_mailbox_models.py` | creates folder, thread, message, attachment, label, messagelabel tables + indexes |

**Services**
| Path | Purpose |
|---|---|
| `backend/app/services/mime_parser.py` | `parse_message()` — RFC822 → structured (subject, addresses, date, body text/html, snippet, attachment list) |
| `backend/app/services/sanitizer.py` | `sanitize_html()` (nh3 allow-list), `classify_remote_content()` (detects external img src) |
| `backend/app/services/sync.py` | `SyncService` class: connect IMAP, discover folders, upsert folders, sync INBOX headers (latest N), status (UIDVALIDITY/UIDNEXT), error handling; `_parse_fetch_response`/`_upsert_message` skeleton |

**Routes**
| Path | Purpose |
|---|---|
| `backend/app/api/v1/folders.py` | GET/POST/GET/PATCH/DELETE /api/v1/folders (tenant-scoped by account ownership) |
| `backend/app/api/v1/messages.py` | GET /api/v1/messages (cursor pagination, folder filter, unread filter), GET /api/v1/messages/{id} |
| `backend/app/api/v1/accounts.py` | added POST /api/v1/accounts/{id}/sync (triggers SyncService) |
| `backend/app/api/v1/api.py` | registers folders + messages routers |

## Verification NOT possible in this environment

| Gate | Blocker |
|---|---|
| Seed GreenMail 500+ messages, sync → DB counts match IMAP STATUS | No Docker/GreenMail |
| IMAP action round-trip (read/move/delete) | No live IMAP |
| p95 list < 150 ms @ 10k messages | No DB |
| XSS corpus neutralized | No test runner |
| Charset decoding (Shift-JIS, ISO-8859, UTF-7) | No test data |
| N+1 query count assert | No test runner |

## Bugs found

None (no live system).

## Known limitations

- `SyncService._parse_fetch_response` and `_upsert_message` are stubs — the IMAP FETCH response parsing needs a live server to implement correctly. Structure (connect, folders, status) is in place.
- Message write-through (flag/move/copy/delete to IMAP then DB) not yet implemented (Phase 4/6).
- Threading (JWZ-style References/In-Reply-To) not yet implemented.

## Next

In an environment with Docker + network:
```bash
cd posthaven
docker compose up -d --build
docker compose exec backend alembic upgrade head
make seed
# create a greenmail account via API, then:
curl -X POST http://localhost:8000/api/v1/accounts/{id}/sync
```

Then proceed to Phase 4 (Real-Time Engine: IDLE → Redis → WebSocket).
