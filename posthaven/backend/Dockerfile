FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    POETRY_VERSION=1.8.3

WORKDIR /app

# System deps (minimal)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libc6-dev \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Non-root user
RUN groupadd -g 1000 appuser && \
    useradd -u 1000 -g appuser -m -s /bin/sh appuser

# Dependencies
COPY pyproject.toml ./
RUN pip install --upgrade pip && pip install -e .

# Application code
COPY --chown=appuser:appuser app ./app
COPY --chown=appuser:appuser alembic.ini alembic.ini
COPY --chown=appuser:appuser alembic ./alembic

USER appuser

# Run migrations then start
ENV PYTHONPATH=/app
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]

EXPOSE 8000
