# Egreen Quanta — developer tasks.
# Windows: use Git Bash / WSL, or run the underlying commands directly.

BACKEND      := backend
FRONTEND     := frontend
VENV         := $(BACKEND)/.venv
ifeq ($(OS),Windows_NT)
PYBIN        := $(VENV)/Scripts
else
PYBIN        := $(VENV)/bin
endif
PY           := $(PYBIN)/python

.DEFAULT_GOAL := help

.PHONY: help
help: ## List targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

# ---------------------------------------------------------------- setup
.PHONY: setup setup-backend setup-frontend
setup: setup-backend setup-frontend ## Install all dependencies

setup-backend: ## Create venv + install backend deps
	python -m venv $(VENV)
	$(PYBIN)/pip install --upgrade pip wheel
	$(PYBIN)/pip install -r $(BACKEND)/requirements-dev.txt

setup-frontend: ## Install frontend deps
	cd $(FRONTEND) && npm install

.PHONY: lock
lock: ## Freeze resolved backend versions to requirements.lock
	$(PYBIN)/pip freeze > $(BACKEND)/requirements.lock

# ---------------------------------------------------------------- database
.PHONY: migrate makemigration
migrate: ## Apply DB migrations
	cd $(BACKEND) && $(PY) -m alembic upgrade head

makemigration: ## Autogenerate a migration: make makemigration m="message"
	cd $(BACKEND) && $(PY) -m alembic revision --autogenerate -m "$(m)"

.PHONY: seed
seed: ## Load demo data (users, trust anchors, sample events)
	cd $(BACKEND) && $(PY) -m app.seeds.seed

# ---------------------------------------------------------------- run
.PHONY: dev dev-backend dev-frontend
dev: ## Run backend + frontend (two terminals recommended; this runs backend, then frontend)
	@echo "Run 'make dev-backend' and 'make dev-frontend' in separate terminals."

dev-backend: ## Backend dev server (SQLite, autoreload)
	cd $(BACKEND) && $(PY) -m uvicorn app.main:app --reload --port 8000

dev-frontend: ## Frontend dev server (Vite)
	cd $(FRONTEND) && npm run dev

# ---------------------------------------------------------------- quality
.PHONY: test test-backend test-frontend lint format typecheck
test: test-backend test-frontend ## Run all tests

test-backend: ## pytest
	cd $(BACKEND) && $(PY) -m pytest

test-frontend: ## vitest
	cd $(FRONTEND) && npm run test

lint: ## ruff + eslint
	cd $(BACKEND) && $(PYBIN)/ruff check .
	cd $(FRONTEND) && npm run lint

format: ## ruff format
	cd $(BACKEND) && $(PYBIN)/ruff format . && $(PYBIN)/ruff check --fix .

typecheck: ## mypy + tsc
	cd $(BACKEND) && $(PYBIN)/mypy app
	cd $(FRONTEND) && npm run typecheck

# ---------------------------------------------------------------- docker
.PHONY: up down logs build
up: ## docker compose up (full stack)
	docker compose up --build

down: ## docker compose down
	docker compose down

logs: ## tail compose logs
	docker compose logs -f

build: ## build images
	docker compose build
