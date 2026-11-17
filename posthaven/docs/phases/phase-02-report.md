# Phase 2 Report — Mail Accounts, IMAP/SMTP Connectivity & Credential Security

**Status:** Code complete; live verification blocked by environment (no Docker daemon, no npm registry access).

## What was created

**Backend**
| Path | Purpose |
|---|---|
| `backend/app/models/account.py` | `MailAccount` table (provider, host, ports, security, username, **encrypted_password**/oauth tokens encrypted, sync state, status, capabilities JSON) + `Identity` table (email, name, signatures, is_default, account/user FKs) + read/create/update/test schemas |
| `backend/app/db/base.py` | imports account models into SQLModel metadata |
| `backend/alembic/versions/0002_phase_02_account_models.py` | migration: create `mailaccount` + `identity` tables + indexes |
| `backend/app/core/crypto.py` | encrypt_credential / decrypt_credential wrappers over Fernet (from security.py) |
| `backend/app/services/imap_client.py` | `ImapClient` class (SSL/STARTTLS/plain, login, CAPABILITY, LIST, SELECT, STATUS, IDLE, logout), SSRF guard (`validate_mail_host` / `_is_private_host` against RFC1918 + link-local + multicast + 169.254 + `ALLOW_PRIVATE_MAIL_HOSTS` flag), `detect_capabilities`, `test_imap_connection` |
| `backend/app/services/smtp_client.py` | `test_smtp_connection` (SSL/STARTTLS/none, login, quit) with SSRF guard |
| `backend/app/services/accounts.py` | create_account (tests IMAP+SMTP before saving, encrypts password), list/get/update/delete accounts, test_account_connection (decrypts stored password for test) |
| `backend/app/api/v1/accounts.py` | GET/POST/GET/PATCH/DELETE /api/v1/accounts, POST /api/v1/accounts/test; tenant-scoped (user_id filter), 404 if not owned |
| `backend/app/api/v1/api.py` | registers accounts router |
| `backend/scripts/seed_greenmail.py` | creates alice@localhost / bob@localhost via GreenMail REST API |
| `backend/pyproject.toml` | added httpx dependency |
| `Makefile` | `make seed` now runs the GreenMail seed script |

**Frontend**
| Path | Purpose |
|---|---|
| `frontend/src/lib/accounts.ts` | typed accounts API client (list/get/create/update/remove/test), `PROVIDER_PRESETS` (greenmail, gmail, outlook, yahoo, fastmail + custom) |
| `frontend/src/pages/AddAccount.tsx` | wizard: provider preset select → credentials → test connection → done; shows capabilities on success |
| `frontend/src/pages/Accounts.tsx` | accounts list table (provider, username, host:port, status chip, sync toggle, remove) |
| `frontend/src/App.tsx` | added /accounts and /add-account routes under PrivateRoute |

## Security notes

- Mail credentials encrypted at rest via Fernet (AES-GCM-compatible) with key derived from `ENCRYPTION_KEY`
- `encrypted_password` is **never** included in `MailAccountRead` API responses
- SSRF guard blocks private/link-local/multicast hosts unless `ALLOW_PRIVATE_MAIL_HOSTS=true` (needed for GreenMail in dev)
- All account endpoints filter by `user_id` (tenant isolation); user B gets 404 for user A's account

## Verification NOT possible in this environment

| Gate | Blocker |
|---|---|
| `docker compose up -d --build` → all healthy | Docker daemon unavailable |
| Alembic migrations (0001 + 0002) upgrade/downgrade | No running Postgres |
| API tests: create account (IMAP+SMTP test), test endpoint, tenant isolation 404, SSRF rejection | No running backend |
| `make seed` (GreenMail accounts) | No running GreenMail |
| Frontend: AddAccount wizard, Accounts list, E2E | No running frontend/backend |
| `ruff`, `mypy`, `tsc`, `eslint` | No deps installed |

## Bugs found

None (no live system). BUGLOG.md remains empty.

## Known limitations

- IMAP IDLE / sync worker not yet implemented (Phase 4). Accounts are created/tested but no mail is synced yet.
- Rate limiter is in-memory dict (single-instance).
- `validate_mail_host` DNS resolution is best-effort and blocking (called once at connect time, acceptable).

## Next

In an environment with Docker + network:
```bash
cd posthaven
docker compose up -d --build
docker compose exec backend alembic upgrade head
make seed   # creates alice@localhost / bob@localhost on GreenMail
```
Test: POST /api/v1/accounts with greenmail credentials (host=mailserver, ports 3143/3025, security=none) → should connect.

Then proceed to Phase 3 (Mailbox Sync Engine: Folders & Messages).
