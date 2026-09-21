SHELL := /usr/bin/env bash

.PHONY: bootstrap check-workspace lint format test build up down

bootstrap:
	uv sync --all-packages
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
	pnpm test

build:
	pnpm build

up:
	bash scripts/deploy.sh up

down:
	bash scripts/deploy.sh down
