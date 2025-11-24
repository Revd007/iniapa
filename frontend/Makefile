.PHONY: help build up down restart logs clean migrate backup

help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Available targets:'
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-15s %s\n", $$1, $$2}'

build: ## Build all Docker images
	docker-compose build

up: ## Start all services
	docker-compose up -d

down: ## Stop all services
	docker-compose down

restart: ## Restart all services
	docker-compose restart

logs: ## Show logs from all services
	docker-compose logs -f

logs-backend: ## Show backend logs
	docker-compose logs -f backend

logs-frontend: ## Show frontend logs
	docker-compose logs -f frontend

logs-db: ## Show database logs
	docker-compose logs -f postgres

clean: ## Remove all containers, volumes, and images
	docker-compose down -v --rmi all

migrate: ## Run database migrations
	docker-compose exec backend python migrate_add_environment.py

init-db: ## Initialize database
	docker-compose exec backend python -c "from app.database import init_db; init_db()"

backup: ## Backup database
	docker-compose exec postgres pg_dump -U tradanalisa tradanalisa > backup_$$(date +%Y%m%d_%H%M%S).sql

restore: ## Restore database (usage: make restore FILE=backup.sql)
	docker-compose exec -T postgres psql -U tradanalisa tradanalisa < $(FILE)

shell-backend: ## Open shell in backend container
	docker-compose exec backend /bin/bash

shell-db: ## Open PostgreSQL shell
	docker-compose exec postgres psql -U tradanalisa tradanalisa

status: ## Show status of all services
	docker-compose ps

health: ## Check health of all services
	@echo "Checking backend health..."
	@curl -s http://localhost:8000/health | jq . || echo "Backend not responding"
	@echo "\nChecking frontend..."
	@curl -s http://localhost:3000 > /dev/null && echo "Frontend is up" || echo "Frontend not responding"

prod-build: ## Build for production
	docker-compose -f docker-compose.yml -f docker-compose.prod.yml build

prod-up: ## Start in production mode
	docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d

