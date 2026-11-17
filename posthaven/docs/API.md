# PostHaven API Reference

Base path: `/api/v1`

## Auth
- `POST /auth/register` — register (first user = admin). Sets httpOnly cookies.
- `POST /auth/login` — login. Sets httpOnly cookies.
- `POST /auth/refresh` — rotate refresh token. Sets new cookies.
- `POST /auth/logout` — revoke refresh token, clear cookies.
- `GET /auth/me` — current user.
- `POST /auth/change-password` — change password, revoke all sessions.

## Accounts
- `GET /accounts` — list user's mail accounts (tenant-scoped).
- `POST /accounts` — create account (tests IMAP+SMTP first, encrypts password).
- `GET /accounts/{id}` — get account (no secrets returned).
- `PATCH /accounts/{id}` — enable/disable sync.
- `DELETE /accounts/{id}` — delete account + cascade.
- `POST /accounts/test` — test IMAP/SMTP connection.
- `POST /accounts/{id}/sync` — trigger folder/message sync.

## Folders
- `GET /accounts?account_id=...` — list folders for an account.
- `POST /folders` — create folder.
- `PATCH /folders/{id}` — update folder.
- `DELETE /folders/{id}` — delete folder.

## Messages
- `GET /messages?folder_id=&cursor=&limit=` — cursor-paginated message list.
- `GET /messages/{id}` — message detail (sanitized HTML).

## Compose
- `GET /compose/drafts` — list drafts.
- `POST /compose/drafts` — upsert (autosave) draft.
- `DELETE /compose/drafts/{id}` — delete draft.
- `GET /compose/scheduled` — list scheduled sends.
- `POST /compose/scheduled` — schedule a send (undo-send / send-later via ARQ).
- `GET /compose/templates` — list templates.
- `POST /compose/templates` — create template.

## Search
- `GET /search?q=...&folder_id=&limit=&offset=` — Gmail-style operators + Postgres FTS.
- `POST /search/saved` — save a search.
- `GET /search/saved` — list saved searches.

## Labels
- `GET /labels` — list labels.
- `POST /labels` — create label.
- `DELETE /labels/{id}` — delete label.

## Rules
- `GET /rules` — list rules.
- `POST /rules` — create rule (conditions x actions).
- `PATCH /rules/{id}` — update rule.
- `DELETE /rules/{id}` — delete rule.

## Snooze
- `POST /snooze` — snooze a message (set wake_at).
- `GET /snooze` — list active snoozes.

## Contacts
- `GET /contacts` — list contacts (search + group filter).
- `POST /contacts` — create contact.
- `GET /contacts/{id}` — get contact.
- `PATCH /contacts/{id}` — update contact.
- `DELETE /contacts/{id}` — delete contact.
- `GET /contacts/autocomplete?q=` — contact autocomplete.
- `GET /contacts/groups` — list contact groups.
- `POST /contacts/groups` — create contact group.

## Settings
- `GET /settings` — list user settings.
- `POST /settings/{key}` — upsert a setting.

## Admin (admin-only)
- `GET /admin/users` — list all users.
- `PATCH /admin/users/{user_id}` — toggle is_active/is_admin.
- `GET /admin/health` — system health (user count).

## Health
- `GET /health` — liveness.
- `GET /health/ready` — readiness (DB + Redis).

WebSocket: `GET /ws` (auth via `access_token` cookie).
