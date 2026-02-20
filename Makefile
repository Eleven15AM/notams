# NOTAM System Makefile
# Commands for local development and testing

.PHONY: help build build-base build-test build-app clean test test-unit test-integration \
        test-coverage run run-once run-background stop logs logs-follow restart \
        report-active report-drone report-stats report-by-airport report-today \
        query query-drone query-recent check-env rebuild clean-cache

.PHONY: help init build run-once run-background logs stop test test-unit test-coverage reports \
        search search-background load-aerodromes purge db-shell report-search report-priority

.DEFAULT_GOAL := help

# Color output
BLUE := \033[0;34m
GREEN := \033[0;32m
YELLOW := \033[0;33m
RED := \033[0;31m
NC := \033[0m # No Color

# Load environment variables from .env if it exists
ifneq (,$(wildcard .env))
    include .env
    export
endif

##@ General

help: ## Display this help message
	@echo "$(BLUE)NOTAM Monitoring System - Available Commands$(NC)"
	@echo ""
	@echo "$(YELLOW)Quick Start (Local Development):$(NC)"
	@echo "  make init              # Initialize project"
	@echo "  make build             # Build Docker images locally"
	@echo "  make run-once          # Run single update"
	@echo "  make reports           # View reports"
	@echo ""
	@echo "$(YELLOW)Production (Pre-built Images):$(NC)"
	@echo "  make -f Makefile.prod help-prod              # Show production commands"
	@echo "  make -f Makefile.prod run-background-prod   # Start service"
	@echo "  make -f Makefile.prod reports-prod          # Generate reports"
	@echo "  make -f Makefile.prod logs-prod             # View logs"
	@echo ""
	@echo "$(YELLOW)Search Modes (New):$(NC)"
	@echo "  make search              # Run free-text search once"
	@echo "  make search-background   # Run continuous free-text search"
	@echo "  make report-search       # Show NOTAMs by search term"
	@echo "  make report-priority     # Show high priority NOTAMs"
	@echo ""
	@echo "$(YELLOW)Aerodrome Data:$(NC)"
	@echo "  make load-aerodromes     # Download and load OurAirports CSV"
	@echo ""
	@echo "$(YELLOW)Database Maintenance:$(NC)"
	@echo "  make purge               # Run database purge routines"
	@echo "  make db-shell            # Open SQLite shell"
	@echo ""
	@awk 'BEGIN {FS = ":.*##"; printf "\n"} /^[a-zA-Z_-]+:.*?##/ { printf "  $(GREEN)%-20s$(NC) %s\n", $$1, $$2 } /^##@/ { printf "\n$(YELLOW)%s$(NC)\n", substr($$0, 5) } ' $(MAKEFILE_LIST)
	@echo ""
	@echo "$(YELLOW)For production deployment help:$(NC) make -f Makefile.prod help-prod"
	@echo ""

##@ Setup

init: ## Initialize project (create dirs, copy env example)
	@echo "$(BLUE)Initializing project...$(NC)"
	@mkdir -p data queries src tests backups
	@touch src/__init__.py tests/__init__.py
	@if [ ! -f .env ]; then \
		cp .env.example .env && \
		echo "$(GREEN) Created .env file from .env.example$(NC)"; \
	else \
		echo "$(YELLOW) .env already exists, skipping$(NC)"; \
	fi
	@chmod +x run_query.sh 2>/dev/null || true
	@echo "$(GREEN) Project initialized$(NC)"

setup: init build ## Complete setup (init + build all images)
	@echo "$(GREEN) Setup complete! Try 'make run-once' to start$(NC)"

check-env: ## Verify .env file exists and is configured
	@if [ ! -f .env ]; then \
		echo "$(RED) .env file not found!$(NC)"; \
		echo "$(YELLOW)Run 'make init' to create it$(NC)"; \
		exit 1; \
	fi
	@echo "$(GREEN) .env file found$(NC)"
	@echo "$(BLUE)Current configuration:$(NC)"
	@grep -E '^[A-Z_]+=.+' .env | grep -v API_KEY

##@ Build

build: ## Build all Docker images (base, test, app)
	@echo "$(BLUE)Building all Docker images...$(NC)"
	@docker-compose build
	@echo "$(GREEN) All images built successfully$(NC)"

build-base: ## Build only base image with dependencies
	@echo "$(BLUE)Building base image...$(NC)"
	@docker build --target base -t notam-base .
	@echo "$(GREEN) Base image built$(NC)"

build-test: ## Build test image
	@echo "$(BLUE)Building test image...$(NC)"
	@docker build --target test -t notam-test .
	@echo "$(GREEN) Test image built$(NC)"

build-app: ## Build application image
	@echo "$(BLUE)Building application image...$(NC)"
	@docker build --target app -t notam-app .
	@echo "$(GREEN) Application image built$(NC)"

rebuild: clean build ## Clean and rebuild all images
	@echo "$(GREEN) Rebuild complete$(NC)"

##@ Run Application (Local Development)

run: check-env ## Run continuous monitoring (foreground)
	@echo "$(BLUE)Starting NOTAM monitoring (continuous mode)...$(NC)"
	@echo "$(YELLOW)Press Ctrl+C to stop$(NC)"
	@docker-compose up notam-app

run-once: check-env ## Run single update cycle
	@echo "$(BLUE)Running single NOTAM update...$(NC)"
	@docker-compose run --rm notam-app python -m src.main --once
	@echo "$(GREEN) Update complete$(NC)"

run-background: check-env ## Run in background (daemon mode)
	@echo "$(BLUE)Starting NOTAM monitoring in background...$(NC)"
	@docker-compose up -d notam-app
	@echo "$(GREEN) Running in background$(NC)"
	@echo "$(YELLOW)View logs: make logs-follow$(NC)"
	@echo "$(YELLOW)Stop: make stop$(NC)"

stop: ## Stop all docker-compose containers
	@echo "$(BLUE)Stopping all containers...$(NC)"
	@docker-compose down
	@echo "$(GREEN) All containers stopped$(NC)"

restart: stop run-background ## Restart background service

##@ Testing

test: ## Run all tests
	@echo "$(BLUE)Running all tests...$(NC)"
	@docker-compose run --rm notam-test pytest -v tests/

test-unit: ## Run only unit tests
	@echo "$(BLUE)Running unit tests...$(NC)"
	@docker-compose run --rm notam-test pytest tests/test_parser.py tests/test_database.py -v

test-integration: ## Run only integration tests
	@echo "$(BLUE)Running integration tests...$(NC)"
	@docker-compose run --rm notam-test pytest tests/test_integration.py -v

test-coverage: ## Run tests with coverage report
	@echo "$(BLUE)Running tests with coverage...$(NC)"
	@docker-compose run --rm notam-test pytest --cov=src --cov-report=term-missing --cov-report=html
	@echo "$(GREEN) Coverage report generated in htmlcov/$(NC)"

##@ Reports (Local Development)

report-active: ## Show all active airport closures
	@echo "$(BLUE)Active Airport Closures:$(NC)"
	@docker-compose run --rm notam-query python -m src.reports active

report-today: ## Show today's airport closures
	@echo "$(BLUE)Today's Airport Closures:$(NC)"
	@docker-compose run --rm notam-query python -m src.reports today

# report-drone: ## Show drone-related closures
# 	@echo "$(BLUE)Drone-Related Closures:$(NC)"
# 	@docker-compose run --rm notam-query python -m src.reports drone

# report-stats: ## Show summary statistics
# 	@echo "$(BLUE)NOTAM Statistics:$(NC)"
# 	@docker-compose run --rm notam-query python -m src.reports stats

report-by-airport: ## Show closures grouped by airport
	@echo "$(BLUE)Closures by Airport:$(NC)"
	@docker-compose run --rm notam-query python -m src.reports by-airport

reports: report-stats report-drone report-today report-active ## Run all reports

##@ Custom Queries (Local Development)

query: ## Run custom SQL query (usage: make query FILE=queries/your_query.sql)
	@if [ -z "$(FILE)" ]; then \
		echo "$(RED) Please specify query file: make query FILE=queries/your_query.sql$(NC)"; \
		exit 1; \
	fi
	@if [ ! -f "$(FILE)" ]; then \
		echo "$(RED) Query file not found: $(FILE)$(NC)"; \
		exit 1; \
	fi
	@echo "$(BLUE)Running query: $(FILE)$(NC)"
	@docker-compose run --rm notam-query python -m src.reports query $(FILE)

query-drone: ## Run drone closures query
	@make query FILE=queries/drone_closures.sql

query-recent: ## Run recent closures query
	@make query FILE=queries/recent_closures.sql

##@ Logs

logs: ## Show recent logs
	@docker-compose logs --tail=50 notam-app

logs-follow: ## Follow logs in real-time
	@docker-compose logs -f notam-app

##@ Free-Text Search

search: check-env ## Run free-text NOTAM search (once)
	docker-compose run --rm notam-app python -m src.main --mode search --once

search-background: check-env ## Run free-text search in background (continuous)
	docker-compose up -d notam-app
	docker-compose exec -d notam-app python -m src.main --mode search

##@ Aerodrome Data

load-aerodromes: check-env ## Download and load OurAirports CSV into database
	@echo "$(BLUE)Downloading and loading OurAirports CSV...$(NC)"
	@docker-compose run --rm notam-app python -m src.aerodrome_loader --download
	@echo "$(GREEN) Aerodrome data loaded$(NC)"

##@ Database Maintenance

purge: check-env ## Run database purge routines (expired, cancelled, old search runs)
	@echo "$(BLUE)Running database purge routines...$(NC)"
	@docker-compose run --rm notam-app python -m src.database_cli --purge-all
	@echo "$(GREEN) Purge complete$(NC)"

db-shell: ## Open SQLite shell to local database
	docker-compose run --rm notam-app sqlite3 /app/data/notam.db

##@ Reports (updated)

report-search: check-env ## Show NOTAMs by search term
	docker-compose run --rm notam-query python -m src.reports search-term

report-priority: check-env ## Show high priority NOTAMs ordered by score
	docker-compose run --rm notam-query python -m src.reports priority

report-stats: check-env ## Show summary statistics
	docker-compose run --rm notam-query python -m src.reports stats

report-closures: check-env ## Show active closures
	docker-compose run --rm notam-query python -m src.reports closures

report-drone: check-env ## Show drone-related NOTAMs
	docker-compose run --rm notam-query python -m src.reports drone

##@ Cleanup

clean: ## Remove Docker images and containers
	@echo "$(BLUE)Cleaning up Docker resources...$(NC)"
	@docker-compose down --rmi local 2>/dev/null || true
	@echo "$(GREEN) Docker resources cleaned$(NC)"

clean-cache: ## Remove Python cache files
	@echo "$(BLUE)Removing cache files...$(NC)"
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@find . -type f -name "*.pyo" -delete 2>/dev/null || true
	@find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	@rm -rf htmlcov/ .coverage 2>/dev/null || true
	@echo "$(GREEN) Cache files removed$(NC)"