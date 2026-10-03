.PHONY: setup run demo test lint fmt eval feature docker lanes

setup:  ## create venv and install everything
	python -m venv .venv && . .venv/bin/activate && pip install -e ".[dev]" && cp -n .env.example .env || true

run:    ## start the demo app with the provider from .env
	streamlit run app/streamlit_app.py

demo:   ## offline rehearsal: fake provider, no key, no network
	LLM_PROVIDER=fake streamlit run app/streamlit_app.py

test:
	pytest

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
	docker build -t hackkit . && docker run --rm -p 8501:8501 --env-file .env hackkit

lanes:  ## rebuild the workflow block of docs/DAY_OF.md; optional: make lanes SET="T1=merged T2=doing"
	python scripts/lanes.py $(if $(SET),--set $(SET))
