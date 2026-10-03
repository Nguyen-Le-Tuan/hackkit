.PHONY: setup run demo web snapshot web-test test lint fmt eval feature docker lanes

PORT ?= 8000
HOST ?= 127.0.0.1
WEB_PORT ?= 8600
UVICORN = uvicorn --factory hackkit.server:create_app --host $(HOST) --port $(PORT)

setup:  ## create venv and install everything
	python -m venv .venv && . .venv/bin/activate && pip install -e ".[dev]" && (cp -n .env.example .env || true) && $(MAKE) --no-print-directory hooks

run:    ## API + web UI on http://localhost:8000 with the provider from .env (auto-reload); HOST=0.0.0.0 for LAN
	@echo "Open http://localhost:$(PORT)  (API docs: /api/docs, demo check: /#/doctor)"
	$(UVICORN) --reload --reload-dir src

demo:   ## offline rehearsal: fake provider, no key, no network
	@echo "Open http://localhost:$(PORT)"
	LLM_PROVIDER=fake $(UVICORN)

web:    ## static mode only (what GitHub Pages serves): the UI reads web/snapshots/
	@echo "Open http://localhost:$(WEB_PORT)/?static=1"
	python -m http.server $(WEB_PORT) --bind 127.0.0.1 -d web

snapshot: ## save API responses to web/snapshots/ (run once with the REAL model before the demo)
	python -m hackkit.snapshot

web-test: ## unit tests for the pure JS modules (needs Node 20+)
	node --test web/tests/*.test.mjs

test:   ## Python tests, then JS tests if Node is installed
	pytest
	@if command -v node >/dev/null; then node --test web/tests/*.test.mjs; else echo "(node not found: skipped web tests)"; fi

lint:
	ruff check . && ruff format --check .

fmt:
	ruff check . --fix && ruff format .

eval:   ## score every labeled case file; writes evals/results/<name>.md
	@for f in evals/cases/*.jsonl; do \
	  echo "== $$f"; \
	  python -m hackkit.evals "$$f" --out "evals/results/$$(basename $$f .jsonl).md" || exit 1; \
	done

feature: ## make feature NAME=intake_triage TITLE="Intake triage"
	python -m hackkit.scaffold $(NAME) "$(TITLE)"

docker:
	docker build -t hackkit . && docker run --rm -p 8000:8000 --env-file .env hackkit

lanes:  ## rebuild the workflow block of docs/DAY_OF.md; optional: make lanes SET="T1=merged T2=doing"
	python scripts/lanes.py $(if $(SET),--set $(SET))

# --- guards (P3) ---
# Rules enforced by machines; configuration in hackkit.toml. Uses the repo venv when present.
.PHONY: hooks guard verify freeze unfreeze freeze-status doctor private public
HK_PY := $(if $(wildcard .venv/bin/python),.venv/bin/python,python3)

hooks:  ## install the pre-commit guard for this clone (make setup should call this)
	git config core.hooksPath scripts/hooks
	@echo "hooks: pre-commit guard installed (scripts/hooks/pre-commit)."
	@echo "hooks: reminder: run 'make hooks' once in every clone; 'make setup' should call it."

guard:  ## check every tracked file: blocked docs, big files, gitlinks, symlinks, secrets
	$(HK_PY) scripts/guard.py --all

verify: ## make verify PR=12 [COMMENT=1] | make verify BRANCH=agent/x (local, no gh)
	@if [ -n "$(PR)" ]; then \
	  $(HK_PY) scripts/verify_pr.py $(PR) $(if $(COMMENT),--comment); \
	elif [ -n "$(BRANCH)" ]; then \
	  $(HK_PY) scripts/verify_pr.py --local $(BRANCH); \
	else echo "usage: make verify PR=<number> [COMMENT=1]  or  make verify BRANCH=<branch>"; exit 2; fi

freeze: ## demo freeze: commit .freeze, protect main; only PRs labeled bugfix pass CI
	$(HK_PY) scripts/freeze.py freeze

unfreeze: ## lift the demo freeze
	$(HK_PY) scripts/freeze.py unfreeze

freeze-status: ## is main frozen? since when, by whom
	$(HK_PY) scripts/freeze.py status

doctor: ## demo-machine check: python, deps, .env, port, power, screen
	$(HK_PY) scripts/doctor.py

private: ## make the GitHub repo private (asks first)
	$(HK_PY) scripts/visibility.py private

public: ## make the GitHub repo public, after the guard passes (asks first)
	$(HK_PY) scripts/visibility.py public
