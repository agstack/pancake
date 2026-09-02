# PnD DPI OpenScience demo -- orchestration helpers.
# Usage: make demo   (clone deps, generate keys+env, bring the stack up)

SHELL := /bin/bash
AGSTACK_ROOT := $(abspath ../../)
AR2_DIR := $(AGSTACK_ROOT)/ar2
HUB_DIR := $(AGSTACK_ROOT)/ar2-hub
PIN_TAG := v0.9-review

.PHONY: demo core clone-deps clone-openscience keys env up openscience down logs notebook notebook-pnd notebook-openscience openscience-notebook-source clean

demo: clone-deps env core ## Full demo: deps + env + core stack

core: env ## Bring up the core stack (pancake + tap + pnd + postgres)
	docker compose --profile core up --build

up: env ## Bring up everything including AR2 hub + node
	docker compose --profile core --profile registry up --build

openscience: env ## Bring up everything plus the terrapipe-os node (EUDR screen, NDVI, GFS)
	docker compose --profile core --profile registry --profile openscience up --build

down: ## Stop the stack
	docker compose --profile core --profile registry --profile openscience down

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
	@$(MAKE) --no-print-directory clone-openscience

# terrapipe-os is a private repository today, so this is expected to fail for
# most people and must not take the rest of the demo down with it. The core and
# registry profiles do not depend on it; only `make openscience` does. Saying so
# here is the difference between a reviewer knowing the open-science half is
# unavailable to them and a reviewer debugging a compose build error.
clone-openscience: ## Clone terrapipe-os if access allows (private; optional)
	@dir="$(AGSTACK_ROOT)/terrapipe-os"; \
	if [ -d "$$dir/.git" ]; then \
	  echo "terrapipe-os present at $$dir"; \
	elif git clone --quiet git@github.com:sumerjohal/terrapipe-os.git "$$dir" 2>/dev/null; then \
	  echo "Cloned terrapipe-os -> $$dir"; \
	else \
	  echo "terrapipe-os not cloned: it is private and this machine has no access."; \
	  echo "  'make demo', 'make core' and 'make up' are unaffected."; \
	  echo "  'make openscience' and the deforestation/NDVI/GFS half of the"; \
	  echo "  open-science notebook need it; those cells report SKIPPED with"; \
	  echo "  that reason rather than failing."; \
	fi

keys: ## Generate a Pancake issuer keypair into .env
	@python -m pancake_services.grants.testkit.mint_test_credentials --keygen 2>/dev/null || true

env: ## Create .env from .env.example with a generated issuer key (idempotent)
	@python3 gen_env.py

notebook: notebook-pnd notebook-openscience ## Execute both demo notebooks headless

notebook-pnd: ## Execute the PnD traceability notebook headless
	jupyter nbconvert --to notebook --execute pnd_dpi_demo.ipynb --output pnd_dpi_demo.executed.ipynb

# --allow-errors, because the point of this notebook is that it records what did
# not run. A cell that cannot reach a service marks itself SKIPPED and the run
# continues; aborting on the first unreachable service would leave the ledger at
# the end -- the only honest summary of what was demonstrated -- unwritten.
notebook-openscience: openscience-notebook-source ## Execute the open-science notebook headless
	jupyter nbconvert --to notebook --execute --allow-errors \
	  openscience_dpi_demo.ipynb --output openscience_dpi_demo.executed.ipynb

# The notebook is generated, never hand-edited. Regenerating before running it
# means a committed .ipynb that has drifted from the script cannot be what gets
# executed and reported.
openscience-notebook-source: ## Regenerate the open-science notebook from its source script
	python3 build_openscience_notebook.py

clean: down ## Stop stack and remove generated env
	rm -f .env pnd_dpi_demo.executed.ipynb openscience_dpi_demo.executed.ipynb

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  %-14s %s\n", $$1, $$2}'
