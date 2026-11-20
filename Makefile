.PHONY: setup format format-python format-web lint lint-python lint-web test \
	web-dev web-build test-db-up test-db-down test-database test-e2e \
	prod-up prod-down prod-logs

setup:
	uv sync --all-packages
	npm install
	uv run pre-commit install

format: format-python format-web

format-python:
	uv run ruff check --fix api
	uv run black api

format-web:
	npm run format --workspace web

lint: lint-python lint-web

lint-python:
	uv run ruff check api
	uv run black --check api

lint-web:
	npm run lint --workspace web
	npm run format:check --workspace web

test:
	uv run pytest

web-dev:
	npm run dev --workspace web

web-build:
	npm run build --workspace web

test-db-up:
	docker compose up -d --wait database-test

test-db-down:
	docker compose down -v

test-database: test-db-up
	uv run pytest

test-e2e: test-db-up
	cd api && CIVIC_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:55432/civic_test uv run alembic upgrade head
	cd web && npm run test:e2e

prod-up:
	docker compose -f docker-compose.prod.yml up -d --build

prod-down:
	docker compose -f docker-compose.prod.yml down -v

prod-logs:
	docker compose -f docker-compose.prod.yml logs -f
