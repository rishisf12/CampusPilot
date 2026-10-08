# Backend Dockerfile
FROM python:3.11-slim

WORKDIR /app

# System dependencies.
# libpq-dev is kept even though psycopg[binary] ships its own libpq: the binary
# wheel only covers the common platforms, and falling back to a source build
# here is cheaper than discovering a missing wheel on an unusual arch.
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code. Alembic lives at backend/alembic, next to the package,
# and the migration command in docker-compose refers to it by that path.
COPY backend/backend ./backend
COPY backend/alembic.ini ./backend/alembic.ini
COPY backend/alembic ./backend/alembic
COPY tools ./tools
COPY database ./database

# Create uploads directory
RUN mkdir -p /app/backend/uploads

# The package directory has to be importable by its bare names.
#
# The application uses flat imports throughout - `from core.database import ...`,
# `from features.monitoring import ...` - because that is what the tests, the
# Alembic env.py and the local tooling all do. That means `/app/backend` has to
# be on sys.path, not just `/app`.
#
# Without this the container starts and immediately dies with
# `ModuleNotFoundError: No module named 'core'`: `uvicorn backend.main:app`
# resolves the outer `backend` package fine, then the module's own imports fail.
# It is worth calling out because the failure looks like a missing file rather
# than a path problem.
ENV PYTHONPATH=/app/backend

# Expose port
EXPOSE 8001

# Run with uvicorn.
#
# The app runs `alembic upgrade head` in its lifespan hook (see
# core/database.py), so there is no separate migration step to remember. It is
# safe on every boot because Alembic is a no-op when the version table already
# says "head", and it refuses to start rather than half-apply.
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8001"]