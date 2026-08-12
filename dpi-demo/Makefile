# PnD DPI OpenScience demo -- orchestration helpers.
# Usage: make demo   (clone deps, generate keys+env, bring the stack up)

SHELL := /bin/bash
AGSTACK_ROOT := $(abspath ../../)
AR2_DIR := $(AGSTACK_ROOT)/ar2
HUB_DIR := $(AGSTACK_ROOT)/ar2-hub
PIN_TAG := v0.9-review

.PHONY: demo core clone-deps keys env up down logs notebook clean

demo: clone-deps env core ## Full demo: deps + env + core stack

core: env ## Bring up the core stack (pancake + tap + pnd + postgres)
	docker compose --profile core up --build

up: env ## Bring up everything including AR2 hub + node
	docker compose --profile core --profile registry up --build

down: ## Stop the stack
	docker compose --profile core --profile registry down

logs: ## Tail logs
	docker compose logs -f

clone-deps: ## Clone/checkout ar2 + ar2-hub at the pinned demo tag
	@for repo in ar2 ar2-hub; do \
	  dir="$(AGSTACK_ROOT)/$$repo"; \
	  if [ ! -d "$$dir/.git" ]; then \
	    echo "Cloning $$repo -> $$dir"; \
	    git clone https://github.com/agstack/$$repo.git "$$dir"; \
	  fi; \
	  echo "Checking out $(PIN_TAG) in $$repo"; \
	  git -C "$$dir" fetch --tags --quiet || true; \
	  git -C "$$dir" checkout $(PIN_TAG) 2>/dev/null || echo "  (tag $(PIN_TAG) not found; leaving current checkout)"; \
	done

keys: ## Generate a Pancake issuer keypair into .env
	@python -m pancake_services.grants.testkit.mint_test_credentials --keygen 2>/dev/null || true

env: ## Create .env from .env.example with a generated issuer key (idempotent)
	@python3 gen_env.py

notebook: ## Execute the demo notebook headless
	jupyter nbconvert --to notebook --execute pnd_dpi_demo.ipynb --output pnd_dpi_demo.executed.ipynb

clean: down ## Stop stack and remove generated env
	rm -f .env pnd_dpi_demo.executed.ipynb

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  %-14s %s\n", $$1, $$2}'
