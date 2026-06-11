# Freqtrade Control Plane — developer & deployment shortcuts.
# Run `make` or `make help` to list targets.

PORT        ?= 9000
EXCHANGE    ?= kraken
BOT_DATA_ROOT ?= /srv/control-plane/bots
BACKUP_DIR  ?= ./backups
COMPOSE     := docker compose -f deploy/docker-compose.yml
PY          := backend/.venv/bin

.DEFAULT_GOAL := help
.PHONY: help install install-backend install-frontend env secrets \
        backend frontend dev-start dev-stop build dev up down restart logs ps \
        pull-freqtrade backup clean

help: ## Show this help
	@echo "Freqtrade Control Plane — make targets:" && echo
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-18s\033[0m %s\n",$$1,$$2}'
	@echo
	@echo "Dev:    make install env && (make backend) and (make frontend) in two terminals"
	@echo "Deploy: edit deploy/Caddyfile + backend/.env, then make pull-freqtrade build up"

# --- Setup ---------------------------------------------------------------

install: install-backend install-frontend ## Install backend venv + frontend deps

install-backend: ## Create the backend venv and install requirements
	python3 -m venv backend/.venv
	$(PY)/pip install --upgrade pip
	$(PY)/pip install -r backend/requirements.txt

install-frontend: ## Install frontend npm dependencies
	npm --prefix frontend install

env: ## Create backend/.env from the example with generated secrets (if missing)
	@if [ -f backend/.env ]; then \
		echo "backend/.env already exists — not overwriting"; \
	else \
		cp backend/.env.example backend/.env; \
		python3 -c "import secrets;print('CP_JWT_SECRET='+secrets.token_urlsafe(48))" >> backend/.env; \
		python3 -c "import os,base64;print('CP_FERNET_KEY='+base64.urlsafe_b64encode(os.urandom(32)).decode())" >> backend/.env; \
		echo "Created backend/.env with generated secrets."; \
		echo "Now set CP_BOOTSTRAP_ADMIN_EMAIL / _PASSWORD and CP_PUBLIC_ORIGIN."; \
	fi

secrets: ## Print freshly generated CP_JWT_SECRET and CP_FERNET_KEY (to paste into .env)
	@python3 -c "import secrets;print('CP_JWT_SECRET='+secrets.token_urlsafe(48))"
	@python3 -c "import os,base64;print('CP_FERNET_KEY='+base64.urlsafe_b64encode(os.urandom(32)).decode())"

# --- Dev (run each in its own terminal) ----------------------------------

backend: ## Run the backend in dev mode (reload) on :$(PORT)
	cd backend && CP_BOT_DATA_ROOT=$(CURDIR)/backend/_test_bots \
		CP_BOT_ADDRESS_MODE=docker_ip CP_DEFAULT_EXCHANGE=$(EXCHANGE) \
		.venv/bin/uvicorn app.main:app --reload --port $(PORT)

frontend: ## Run the frontend dev server on :5173 (proxies /api -> :$(PORT))
	npm --prefix frontend run dev

dev-start: ## Start backend + frontend in the background (quick local testing)
	@cd backend && CP_BOT_DATA_ROOT=$(CURDIR)/backend/_test_bots \
		CP_BOT_ADDRESS_MODE=docker_ip CP_DEFAULT_EXCHANGE=$(EXCHANGE) \
		nohup .venv/bin/uvicorn app.main:app --reload --port $(PORT) > /tmp/cp-backend.log 2>&1 &
	@nohup npm --prefix frontend run dev > /tmp/cp-frontend.log 2>&1 &
	@sleep 2
	@echo "Backend  -> http://localhost:$(PORT)  (log: /tmp/cp-backend.log)"
	@echo "Frontend -> http://localhost:5173      (log: /tmp/cp-frontend.log)"
	@echo "Stop with: make dev-stop"

dev-stop: ## Stop the background dev backend + frontend
	-@pkill -f "uvicorn app.main" 2>/dev/null || true
	-@pkill -f "node.*vite" 2>/dev/null || true
	@echo "Stopped dev backend + frontend."

# --- Deploy (production via docker compose) -------------------------------

pull-freqtrade: ## Pre-pull the official Freqtrade image
	docker pull freqtradeorg/freqtrade:stable

build: ## Build the control-plane image
	$(COMPOSE) build

up: ## Start the stack (caddy + control plane) in the background
	$(COMPOSE) up -d

dev: build up ## Build and start the full stack

down: ## Stop the stack
	$(COMPOSE) down

restart: down up ## Restart the stack

logs: ## Follow control-plane logs
	$(COMPOSE) logs -f control-plane

ps: ## Show stack container status
	$(COMPOSE) ps

# --- Ops -----------------------------------------------------------------

backup: ## Back up every user's bot data (CP_BOT_DATA_ROOT -> $(BACKUP_DIR))
	CP_BOT_DATA_ROOT=$(BOT_DATA_ROOT) scripts/backup_bots.sh $(BACKUP_DIR)

clean: ## Stop dev servers/bot containers and remove local dev state
	-docker ps -aq --filter "name=cp-bot-" | xargs -r docker rm -f
	-pkill -f "uvicorn app.main" 2>/dev/null || true
	-pkill -f "vite" 2>/dev/null || true
	rm -f backend/control_plane.sqlite
	rm -rf backend/_test_bots
