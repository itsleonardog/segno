.PHONY: setup format format-python format-web lint lint-python lint-web test \
	web-dev web-build test-db-up test-db-down test-database

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
