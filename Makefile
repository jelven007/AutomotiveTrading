SHELL := /usr/bin/env bash

.PHONY: bootstrap check-workspace lint format test build up down

bootstrap:
	uv sync --all-packages
	uv sync --directory services/mootdx-collector --frozen
	pnpm install --frozen-lockfile=false

check-workspace:
	bash scripts/check_workspace.sh

lint:
	uv run ruff format --check .
	uv run ruff check .
	pnpm lint

format:
	uv run ruff format .
	uv run ruff check --fix .
	pnpm exec prettier --write "**/*.{css,html,json,js,jsx,md,ts,tsx,yaml,yml}"

test:
	uv run pytest
	uv run --directory services/mootdx-collector pytest
	pnpm test

build:
	pnpm build

up:
	docker compose --env-file infra/compose/.env \
		-f infra/compose/docker-compose.yml up -d
	bash scripts/wait_for_services.sh

down:
	docker compose --env-file infra/compose/.env \
		-f infra/compose/docker-compose.yml down
