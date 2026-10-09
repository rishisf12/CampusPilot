# Contributing

## Getting set up

```bash
git clone https://github.com/rishisf12/CampusPilot.git
cd CampusPilot

# Backend
cd backend
python -m venv .venv && .venv/Scripts/activate     # Windows
pip install -r requirements.txt
cp .env.example backend/backend/.env               # fill in SECRET_KEY + SMTP

# Frontend
cd ../frontend && npm install
```

Run the two servers in separate terminals:

```bash
cd backend/backend && python -m uvicorn main:app --port 8000
cd frontend && npm run dev
```

The backend port **must** match the proxy target in
`frontend/vite.config.ts` (`8000` by default, overridable with
`VITE_DEV_BACKEND`). If you change one, change the other.

Two traps worth knowing before you debug them:

- Keep only **one** `vite.config` file. Vite resolves `vite.config.js` before
  `vite.config.ts`, so a stale `.js` silently wins and your edits to the `.ts`
  do nothing.
- Use `127.0.0.1`, not `localhost`, as the proxy target. `localhost` resolves
  to `::1` first on Windows and uvicorn binds IPv4-only, which turns every
  proxied request into a 500 with an empty body.

Migrations run from `backend/` (where `alembic.ini` lives), not
`backend/backend/`:

```bash
cd backend && python -m alembic -c alembic.ini upgrade head
```

## Before you open a pull request

```bash
cd backend/backend && python -m pytest tests/ -q     # must be green
cd frontend && npm run build                          # must succeed
```

## Code conventions

**Backend**

- Configuration is read through `config.get_settings()`; never hard-code a
  college hour, threshold or branch list in a route or service. Derived
  constants (`COLLEGE_START_HOUR`, `DAYS_ORDER`, `BRANCH_OPTIONS`) live in
  `config.py`.
- Business logic belongs in `services/`, not in `routes/`. Routes validate input
  and serialise output.
- Use `session.exec(select(Model).where(...)).first()` rather than
  `session.get()` / `session.add()` patterns that break under SQLModel, and
  `session.exec(delete(Model))` for bulk clears — `session.exec(select(X)).delete()`
  does **not** exist and raises `AttributeError`.
- Timestamps come from server-side defaults (`server_default=func.now()`);
  `Field(default_factory=…)` is broken under SQLModel 0.0.22 + Pydantic 2.10.
- Every new endpoint that touches user data must declare the
  `get_current_user` dependency. Returning `400` for a bad token is fine;
  returning `200` to an anonymous caller is not.
- Add a test. Parser changes need cases for the awkward input you just fixed —
  that is where the bugs live.

**Frontend**

- All network access goes through `src/api.js`. Components do not call `fetch`.
- Every `await` needs a `try/catch`; surface failures with `ErrorBanner`.
  Unhandled rejections are a bug.
- Shared, non-component data (branch lists, programmes) belongs in
  `constants.js` — exporting constants from a component file breaks Fast Refresh.
- After changing the profile, call `bumpProfileVersion()` so the Exam tab
  refetches.
- Tailwind is loaded via the Play CDN with the palette defined inline in
  `index.html`. Repeatable component classes go in `src/index.css`.

## Adding an endpoint

1. Service function in `services/<domain>_service.py`.
2. Pydantic request/response models in the route module.
3. Route in `routes/<domain>.py`, with `get_current_user` if it is user data.
4. Register in `routes/__init__.py` and include it in `main.py`.
5. Add it to the API table in `README.md` and to `src/api.js`.
6. Test the happy path **and** the 401 path.

## Changing the database schema

`create_db_and_tables()` creates missing tables and then runs a migration pass
that `ALTER TABLE ... ADD COLUMN` for any column a model gained. It also renames
the legacy `exam_seating.exam_date` to `seating_date`. For a rename or a
destructive change, add an explicit step to `database.py` — never edit or delete
`classpilot.db` by hand in a committed change.

## Git

- Branch from `main`, one topic per branch.
- Write commit messages in the imperative and explain *why*, not *what*.
- Never commit `database/classpilot.db`, `backend/backend/uploads/`, `.env`, or
  `node_modules/` — they are already in `.gitignore`.