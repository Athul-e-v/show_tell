.PHONY: help up down logs restart build dev-backend dev-frontend install test migrate seed clean

# Default target
.DEFAULT_GOAL := help

## ----------------------------------------------------------------------
## 🛠️ HAT CONVERSE - MAKEFILE COMMANDS
## ----------------------------------------------------------------------

help: ## Display available commands
	@echo ""
	@echo "  ================================================================"
	@echo "    ⚡ HAT CONVERSE - FULL-STACK PLATFORM MANAGEMENT ⚡"
	@echo "  ================================================================"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'
	@echo ""

up: ## Start PostgreSQL and FastAPI backend containers with Docker Compose
	@echo "🚀 Starting Docker containers for HAT Converse..."
	docker-compose -f api/docker-compose.yml up -d --build
	@echo "✅ Containers running! Backend available at http://localhost:8000/docs"

down: ## Stop and remove all Docker containers & networks
	@echo "🛑 Stopping Docker containers..."
	docker-compose -f api/docker-compose.yml down

logs: ## Tail logs from running Docker containers
	docker-compose -f api/docker-compose.yml logs -f

restart: down up ## Restart all Docker containers

build: ## Rebuild Docker containers without starting them
	docker-compose -f api/docker-compose.yml build

dev-backend: ## Run FastAPI backend locally with live reload
	@echo "🔥 Starting FastAPI backend locally..."
	cd api && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

dev-frontend: ## Run React frontend locally with Vite
	@echo "🎨 Starting React frontend locally..."
	cd web_app && npm run dev

install: ## Install Python backend dependencies and NPM frontend packages
	@echo "📦 Installing backend requirements..."
	pip install -r api/requirements.txt
	@echo "📦 Installing frontend dependencies..."
	cd web_app && npm install

test: ## Run backend unit & integration tests with pytest
	@echo "🧪 Running pytest suite..."
	cd api && pytest

migrate: ## Run Alembic database migrations
	@echo "🗄️ Running Alembic database migrations..."
	cd api && alembic upgrade head

seed: ## Seed initial data into the database
	@echo "🌱 Seeding initial database records..."
	cd api && python -m app.seed


clean: ## Clean up temporary files, build artifacts, and caches
	@echo "🧹 Cleaning caches..."
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	rm -rf web_app/dist api/hat_app.db

COMPOSE_PROD = docker compose --env-file .env.production -f compose.prod.yml

.PHONY: prod-config prod-build prod-up prod-down prod-restart prod-logs prod-ps prod-migrate

prod-config:
	$(COMPOSE_PROD) config --quiet

prod-build:
	$(COMPOSE_PROD) build

prod-up:
	$(COMPOSE_PROD) up -d

prod-down:
	$(COMPOSE_PROD) down

prod-restart:
	$(COMPOSE_PROD) restart

prod-logs:
	$(COMPOSE_PROD) logs -f

prod-ps:
	$(COMPOSE_PROD) ps

prod-migrate:
	$(COMPOSE_PROD) exec backend alembic upgrade head

