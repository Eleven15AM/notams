# NOTAM System Makefile
# Commands for local development and testing

.PHONY: help build build-base build-test build-app clean test test-unit test-integration \
        test-coverage run-once-airport run-once-search run-background-airport \
        run-background-search run-background-all run-once run-background search \
        search-background stop logs-airport logs-search logs-follow restart-airport \
        restart-search report-active report-drone report-stats report-by-airport \
        report-today report-search report-priority report-closures \
        query query-drone query-recent check-env rebuild clean-cache \
        load-aerodromes purge db-shell status info setup init reports

.DEFAULT_GOAL := help

# Color output
BLUE  := \033[0;34m
GREEN := \033[0;32m
YELLOW:= \033[0;33m
RED   := \033[0;31m
NC    := \033[0m

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
	@echo "  make init                    # Initialize project"
	@echo "  make build                   # Build Docker images"
	@echo "  make run-once-airport        # Run airport mode once"
	@echo "  make run-once-search         # Run search mode once"
	@echo "  make reports                 # View all reports"
	@echo ""
	@echo "$(YELLOW)Continuous Background Modes:$(NC)"
	@echo "  make run-background-airport  # Airport mode (continuous)"
	@echo "  make run-background-search   # Search mode (continuous)"
	@echo "  make run-background-all      # Both modes simultaneously"
	@echo "  make stop                    # Stop all containers"
	@echo ""
	@echo "$(YELLOW)Production (Pre-built Images):$(NC)"
	@echo "  make -f Makefile.prod help-prod"
	@echo ""
	@awk 'BEGIN {FS = ":.*##"; printf "\n"} /^[a-zA-Z_-]+:.*?##/ { printf "  $(GREEN)%-28s$(NC) %s\n", $$1, $$2 } /^##@/ { printf "\n$(YELLOW)%s$(NC)\n", substr($$0, 5) } ' $(MAKEFILE_LIST)
	@echo ""
	@echo "$(YELLOW)For production deployment:$(NC) make -f Makefile.prod help-prod"
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
	@echo "$(GREEN) Setup complete!$(NC)"

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

build-base: ## Build only base image
	@docker build --target base -t notam-base .
	@echo "$(GREEN) Base image built$(NC)"

build-test: ## Build test image
	@docker build --target test -t notam-test .
	@echo "$(GREEN) Test image built$(NC)"

build-app: ## Build application image
	@docker build --target app -t notam-app .
	@echo "$(GREEN) Application image built$(NC)"

rebuild: clean build ## Clean and rebuild all images

##@ Run — Airport Mode
# Uses the notam-app docker-compose service.
# Requires AIRPORTS to be configured in .env.

run-once-airport: check-env ## Run airport monitoring once and exit
	@echo "$(BLUE)Running airport mode (once)...$(NC)"
	@docker-compose run --rm notam-app python -m src.main --mode airport --once
	@echo "$(GREEN) Done$(NC)"

run-background-airport: check-env ## Start airport mode continuous monitoring (background)
	@echo "$(BLUE)Starting airport monitoring in background...$(NC)"
	@docker-compose up -d notam-app
	@echo "$(GREEN) Running (airport mode)$(NC)"
	@echo "$(YELLOW)Logs: make logs-airport   Stop: make stop$(NC)"

logs-airport: ## Follow airport mode container logs
	@docker-compose logs -f --timestamps notam-app

##@ Run — Search Mode
# Uses the notam-app-search docker-compose service.
# Requires SEARCH_TERMS to be configured in .env.

run-once-search: check-env ## Run free-text search mode once and exit
	@echo "$(BLUE)Running search mode (once)...$(NC)"
	@docker-compose run --rm notam-app-search python -m src.main --mode search --once
	@echo "$(GREEN) Done$(NC)"

run-background-search: check-env ## Start search mode continuous monitoring (background)
	@echo "$(BLUE)Starting search monitoring in background...$(NC)"
	@docker-compose up -d notam-app-search
	@echo "$(GREEN) Running (search mode)$(NC)"
	@echo "$(YELLOW)Logs: make logs-search   Stop: make stop$(NC)"

logs-search: ## Follow search mode container logs
	@docker-compose logs -f --timestamps notam-app-search

##@ Run — Both Modes

run-background-all: check-env ## Start both airport and search modes simultaneously (background)
	@echo "$(BLUE)Starting both monitoring modes in background...$(NC)"
	@docker-compose up -d notam-app notam-app-search
	@echo "$(GREEN) Both modes running$(NC)"
	@echo "$(YELLOW)Logs: make logs-follow   Stop: make stop$(NC)"

##@ Stop / Restart

stop: ## Stop all docker-compose containers
	@echo "$(BLUE)Stopping all containers...$(NC)"
	@docker-compose down
	@echo "$(GREEN) All containers stopped$(NC)"

logs-follow: ## Follow all container logs
	@docker-compose logs -f --timestamps

restart-airport: stop run-background-airport ## Restart airport monitoring
restart-search: stop run-background-search ## Restart search monitoring

# Legacy aliases — kept so existing scripts / habits don't break
run-once: run-once-airport ## Alias: run-once-airport
run-background: run-background-airport ## Alias: run-background-airport
search: run-once-search ## Alias: run-once-search
search-background: run-background-search ## Alias: run-background-search

##@ Testing

test: ## Run all tests
	@echo "$(BLUE)Running all tests...$(NC)"
	@docker-compose run --rm notam-test pytest -v tests/

test-unit: ## Run unit tests only
	@echo "$(BLUE)Running unit tests...$(NC)"
	@docker-compose run --rm notam-test pytest tests/test_notam_model.py tests/test_parser.py tests/test_database.py -v

test-integration: ## Run integration tests only
	@echo "$(BLUE)Running integration tests...$(NC)"
	@docker-compose run --rm notam-test pytest tests/test_integration.py -v

test-coverage: ## Run tests with coverage report
	@echo "$(BLUE)Running tests with coverage...$(NC)"
	@docker-compose run --rm notam-test pytest --cov=src --cov-report=term-missing --cov-report=html
	@echo "$(GREEN) Coverage report in htmlcov/$(NC)"

##@ Reports

reports: report-stats report-drone report-closures report-priority ## Run all reports

report-stats: check-env ## Show summary statistics
	@echo "$(BLUE)NOTAM Statistics:$(NC)"
	@docker-compose run --rm notam-query python -m src.reports stats

report-active: check-env ## Show active NOTAMs
	@echo "$(BLUE)Active NOTAMs:$(NC)"
	@docker-compose run --rm notam-query python -m src.reports active

report-closures: check-env ## Show active closures
	@echo "$(BLUE)Active Closures:$(NC)"
	@docker-compose run --rm notam-query python -m src.reports closures

report-drone: check-env ## Show drone-related NOTAMs
	@echo "$(BLUE)Drone-Related NOTAMs:$(NC)"
	@docker-compose run --rm notam-query python -m src.reports drone

report-priority: check-env ## Show high priority NOTAMs (score >= 50)
	@echo "$(BLUE)High Priority NOTAMs:$(NC)"
	@docker-compose run --rm notam-query python -m src.reports priority

report-search: check-env ## Show NOTAMs by search term
	@echo "$(BLUE)NOTAMs by Search Term:$(NC)"
	@docker-compose run --rm notam-query python -m src.reports search-term

report-by-airport: check-env ## Show NOTAMs grouped by airport
	@echo "$(BLUE)NOTAMs by Airport:$(NC)"
	@docker-compose run --rm notam-query python -m src.reports by-airport

report-today: check-env ## Show today's NOTAMs
	@echo "$(BLUE)Today's NOTAMs:$(NC)"
	@docker-compose run --rm notam-query python -m src.reports today

##@ Custom Queries

query: check-env ## Run custom SQL query (usage: make query FILE=queries/your_query.sql)
	@if [ -z "$(FILE)" ]; then \
		echo "$(RED) Usage: make query FILE=queries/your_query.sql$(NC)"; \
		exit 1; \
	fi
	@if [ ! -f "$(FILE)" ]; then \
		echo "$(RED) Query file not found: $(FILE)$(NC)"; \
		exit 1; \
	fi
	@echo "$(BLUE)Running query: $(FILE)$(NC)"
	@docker-compose run --rm notam-query python -m src.reports query $(FILE)

query-drone: check-env ## Run predefined drone closures query
	@$(MAKE) query FILE=queries/drone_closures.sql

query-recent: check-env ## Run predefined recent closures query
	@$(MAKE) query FILE=queries/recent_closures.sql

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
	@docker-compose run --rm notam-app sqlite3 /app/data/notam.db

##@ Development Utilities

status: ## Show running containers and database status
	@echo "$(BLUE)Container Status:$(NC)"
	@docker-compose ps
	@echo ""
	@if [ -f data/notam.db ]; then \
		echo "$(GREEN) Database found:$(NC)"; \
		ls -lh data/notam.db; \
	else \
		echo "$(YELLOW) Database not found — run a monitoring mode first$(NC)"; \
	fi

info: ## Show project and Docker image information
	@echo "$(BLUE)NOTAM Monitoring System$(NC)"
	@echo ""
	@echo "Docker Images:"
	@docker images | grep notam || echo "  No images built yet"
	@echo ""
	@echo "Containers:"
	@docker-compose ps

##@ Cleanup

clean: ## Remove Docker containers and images
	@echo "$(BLUE)Cleaning up Docker resources...$(NC)"
	@docker-compose down -v --remove-orphans
	@docker image prune -f
	@echo "$(GREEN) Cleanup complete$(NC)"

clean-cache: ## Remove Python cache files
	@echo "$(BLUE)Removing Python cache files...$(NC)"
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@find . -type f -name "*.pyo" -delete 2>/dev/null || true
	@find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	@rm -rf htmlcov/ .coverage 2>/dev/null || true
	@echo "$(GREEN) Cache files removed$(NC)"