.PHONY: up down logs test e2e lint seed ps clean

COMPOSE ?= docker compose

up:
	$(COMPOSE) up -d --build

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f

ps:
	$(COMPOSE) ps

test:
	cd backend && pip install -e ".[dev]" && pytest -q

lint:
	cd backend && ruff check app && ruff format --check app && mypy app
	cd frontend && npm run lint && npm run typecheck

seed:
	python backend/scripts/seed_greenmail.py

trickle:
	python backend/scripts/trickle.py

clean:
	$(COMPOSE) down -v
	rm -rf backend/.venv frontend/node_modules
