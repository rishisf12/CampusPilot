# Phase 1 Report — Auth, Users & Multi-Tenancy

**Status:** Code complete; live verification blocked by environment (no Docker daemon, no npm registry access).

## What was created

**Backend**
| Path | Purpose |
|---|---|
| `backend/app/models/user.py` | `User` table (id, email, display_name, is_admin, is_active, email_verified, password_hash, timestamps) + `UserRead`/`UserCreate`/`UserUpdate`/`UserRegisterResponse` schemas |
| `backend/app/models/token.py` | `RefreshToken` table (token_hash, expires_at, revoked, replaced_by_token_hash, user_id FK) + `TokenPair` schema |
| `backend/app/models/setting.py` | `UserSetting` table (user_id, key, value) + read/upsert schemas |
| `backend/app/models/audit.py` | `AuditLog` table (action, resource_type/id, details, ip, user_agent, user_id FK) + read schema |
| `backend/app/models/__init__.py` | package marker |
| `backend/app/db/base.py` | imports all models so SQLModel metadata is populated for Alembic |
| `backend/alembic/versions/0001_phase_01_auth_models.py` | migration: create `user`, `refresh_token`, `user_setting`, `audit_log` tables + indexes |
| `backend/app/core/security.py` | argon2 hashing (passlib), JWT access (15 min) + refresh (7 days) HS256, Fernet encryption at rest (derived from ENCRYPTION_KEY), CSRF token generator |
| `backend/app/core/deps.py` | `get_session` re-export, `get_current_user_optional`, `get_current_user` (401 if no valid session), `get_current_admin` (403 if not admin), `CurrentUser`/`CurrentAdmin` deps |
| `backend/app/services/auth.py` | register (first user = admin, case-insensitive email, rate limited), authenticate (argon2 verify, rate limited), issue_token_pair (single-device session), rotate_refresh_token (reuse detection → revoke family), revoke_refresh_token, revoke_all_user_tokens, change_password (invalidates all sessions), audit logging |
| `backend/app/api/v1/auth.py` | POST /register (201 + set cookies), POST /login, POST /refresh (rotation), POST /logout, GET /me, POST /change-password; httpOnly cookies (Secure in prod, SameSite=lax), consistent error envelope |
| `backend/app/api/v1/api.py` | registers auth router under /api/v1 |

**Frontend**
| Path | Purpose |
|---|---|
| `frontend/src/lib/auth.ts` | typed API client (register/login/refresh/me/logout/changePassword), credentials:include for httpOnly cookies |
| `frontend/src/stores/auth.ts` | Zustand store with persist (sessionStorage), login/register/refresh/logout/fetchMe/changePassword, isLoading flag for session hydration |
| `frontend/src/pages/Login.tsx` | email/password form, error state, loading state, link to register |
| `frontend/src/pages/Register.tsx` | display name/email/password (min 8) form, error state, auto-navigate to /health on success |
| `frontend/src/App.tsx` | public /login + /register routes; PrivateRoute wrapper calling fetchMe() on mount, redirects unauthenticated to /login |

## Verification NOT possible in this environment

| Gate | Blocker |
|---|---|
| `docker compose up -d --build` → all healthy | Docker daemon unavailable |
| Alembic `upgrade head` / `downgrade base` | No running Postgres |
| API tests: register→login→me→refresh→logout; refresh reuse revokes family; rate limit; 404 tenant isolation | No running backend |
| Playwright E2E: register → empty inbox → reload stays logged in → logout | No running frontend/backend |
| `ruff check`, `mypy`, `tsc --noEmit`, `eslint` | No Python deps / npm install |

## Bugs found

None (no live system to test). Logged in BUGLOG.md as empty.

## Known limitations (to address in later phases)

- Rate limiter is in-memory dict (single-instance). Will be replaced with Redis-backed limiter in Phase 10 or when multi-worker is needed.
- Refresh token family revocation on reuse revokes ALL tokens for the user (simple, secure). Chain-based family tracking can be added later.
- `init_db()` in lifespan calls `create_all()` (idempotent, harmless after Alembic). Dev convenience only.

## Next

Move to an environment with Docker + network and run:
```bash
cd posthaven
docker compose up -d --build
# wait for healthy
docker compose exec backend alembic upgrade head
# then test auth endpoints:
curl -c cookies.txt -X POST http://localhost:8000/api/v1/auth/register -H 'Content-Type: application/json' -d '{"email":"a@test.com","password":"secret123"}'
curl -b cookies.txt -c cookies.txt -X POST http://localhost:8000/api/v1/auth/login -H 'Content-Type: application/json' -d '{"email":"a@test.com","password":"secret123"}'
curl -b cookies.txt http://localhost:8000/api/v1/auth/me
```

Then proceed to Phase 2 (Mail Accounts, IMAP/SMTP Connectivity & Credential Security).
