# AGENTS.md

Shared instructions for every coding agent in this repo. Codex reads this file directly; Claude
Code reads it through `CLAUDE.md` (`@AGENTS.md`). Agents PREPARE and BUILD; humans DECIDE.

## Project (FILL ON EVENT DAY)
- Problem: <one sentence: who has what pain>
- User: <the one person who uses this demo>
- Demo flow: <input> -> <processing> -> <output the judges will see>
- Novel feature: <the one thing other teams won't have>
- Sponsor API: <name, docs link, what we call>
- Spec: @docs/spec.md

## What already exists (do not rebuild it)
- `src/hackkit/`: framework. LLM providers (anthropic, groq, ollama, fake), structured extraction
  with validation retry, disk cache, demo mode, HTTP connector, exports, evals, feature scaffold.
- `app/streamlit_app.py`: generic demo shell. It renders any registered feature.
- `src/features/receipt/`: reference example of the feature pattern.
- `scripts/orchestrate.sh`: kickoff-transcript -> planning docs in `docs/agent/` (see its header).
- `scripts/worktree.sh`: isolated worktree + branch per agent.
Event work happens in `src/features/<name>/`, `evals/cases/`, and small UI tweaks.
Change `src/hackkit/` only for a real bug or a missing capability, and say so.

## Feature pattern
- New feature: `python -m hackkit.scaffold <name> "<Title>"`.
- A feature = Pydantic schema (inherit `Reviewable`) + instructions + deterministic `rules()`.
- The LLM only extracts what is written. Math, thresholds, eligibility and scoring live in
  `rules()` as plain Python with tests.
- Give every schema field a `description=`; the model reads them.
- Provide `sample_text` and `sample_response` so the demo runs with LLM_PROVIDER=fake.

## Working with other agents (read before you start a task)
- Read `docs/spec.md` and `docs/TASKS.md` first. They are the single source of truth for what to
  build, who owns which task, and which files each task may touch.
- You work in your own git worktree on your own branch (`agent/<name>`). You cannot see other
  agents' uncommitted work and must not try to. Coordination happens through git and these docs.
- Touch only the files listed for your task. If you need a change in a file you do not own, stop
  and tell the human; do not edit it. Never rename or move shared files and never change a
  function signature listed under "Contract" in `docs/TASKS.md` without the human's approval.
- `docs/TASKS.md` is edited by humans on `main` only. Report your status in your final message.
- Before starting a new task: `git merge main`, then `make test`. Commit small and often so the
  human can merge your branch every ~30 minutes. Do not merge into `main` yourself.
- When asked to review another agent's branch: run `git diff main...<branch>`, report findings,
  and do not edit that branch.

## Hard deadline rules
- Demo freeze 1h30 before the deadline. One working end-to-end flow beats many partial ones.
- If a task looks longer than ~30 minutes, stop and propose a simpler option.
- Never break the working demo.

## Data and security
- Only public or synthetic data. No real personal, sensitive, or partner-confidential data.
- Secrets live in `.env` (git-ignored). Never read, print, log, or commit keys.

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
