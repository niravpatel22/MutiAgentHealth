.PHONY: install lint format test migrate seed-admin load-sample-dataset api web up down

UV ?= uv

install:
	cd backend && $(UV) sync --frozen
	cd frontend && npm ci

migrate:
	cd backend && $(UV) run alembic upgrade head

seed-admin:
	cd backend && $(UV) run python -m app.cli seed-admin

load-sample-dataset:
	cd backend && $(UV) run python -m app.cli load-sample-dataset

lint:
	cd backend && $(UV) run ruff check . && $(UV) run black --check .
	cd frontend && npm run lint && npm run format:check

format:
	cd backend && $(UV) run ruff check --fix . && $(UV) run black .
	cd frontend && npm run format

test:
	cd backend && $(UV) run pytest --cov=app -m "not live_llm"
	cd frontend && npm test

api:
	cd backend && $(UV) run uvicorn app.main:app --reload

web:
	cd frontend && npm run dev

up:
	docker compose up --build

down:
	docker compose down
