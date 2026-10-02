# CLAUDE.md

## Project (FILL ON EVENT DAY)
- Problem: <one sentence: who has what pain>
- User: <the one person who uses this demo>
- Demo flow: <input> -> <processing> -> <output the judges will see>
- Novel feature: <the one thing other teams won't have>
- Sponsor API: <name, docs link, what we call>
- Spec: @docs/spec.md

## What already exists (do not rebuild it)
- `src/hackkit/`: framework. LLM providers (anthropic, ollama, fake), structured extraction with
  validation retry, disk cache, demo mode, HTTP connector, exports, evals, feature scaffold.
- `app/streamlit_app.py`: generic demo shell. It renders any registered feature.
- `src/features/receipt/`: reference example of the feature pattern.
Event work happens in `src/features/<name>/`, `evals/cases/`, and small UI tweaks.
Change `src/hackkit/` only for a real bug or a missing capability, and say so.

## Feature pattern
- New feature: `python -m hackkit.scaffold <name> "<Title>"`.
- A feature = Pydantic schema (inherit `Reviewable`) + instructions + deterministic `rules()`.
- The LLM only extracts what is written. Math, thresholds, eligibility and scoring live in
  `rules()` as plain Python with tests.
- Give every schema field a `description=`; the model reads them.
- Provide `sample_text` and `sample_response` so the demo runs with LLM_PROVIDER=fake.

## Hard deadline rules
- Demo freeze 1h30 before the deadline. One working end-to-end flow beats many partial ones.
- If a task looks longer than ~30 minutes, stop and propose a simpler option.
- Never break the working demo.

## Data and security
- Only public or synthetic data. No real personal, sensitive, or partner-confidential data.
- Secrets live in `.env` (git-ignored). Never print, log, or commit keys.

## Commands
- Setup: `make setup` (or `python -m venv .venv && pip install -e ".[dev]"`)
- Run: `make run` | offline rehearsal: `make demo`
- Test: `pytest` | Lint: `make lint` | Format: `make fmt`
- Eval: `python -m hackkit.evals evals/cases/<feature>.jsonl`

## How to work
- For changes over ~50 lines, write a short plan first and wait for approval.
- Type hints and short docstrings. No unrelated refactors.
- Ask one question when the request is ambiguous.
- Small commits: `feat(features/<name>): ...`, `fix(hackkit): ...`.

## Definition of done
- `pytest` passes, `make lint` is clean, the app runs the demo flow on sample data,
  and `make demo` works with no network.
