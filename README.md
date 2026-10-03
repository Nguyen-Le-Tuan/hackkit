# hackkit

A personal hackathon framework. The infrastructure is done before the event, so event time
goes to four things only: **the problem, one novel feature, the sponsor API, and the demo.**

```
messy input (text, image, PDF)
        |
        v
  LLM extraction  ---->  Pydantic validation  ---(invalid)--->  retry with the errors
        |                                                      (max 2 attempts)
        v
  deterministic rules()  -->  metrics + review flags  -->  Streamlit demo / Markdown / JSON
```

## Why it is built this way

- **The LLM reads; Python decides.** Models are good at turning messy input into fields and bad
  at arithmetic and rules. Every feature splits the two, so the numbers in a demo are checked
  by code, not guessed.
- **Uncertainty is shown, not hidden.** Schemas inherit `Reviewable`, so the model reports its
  confidence and the fields it guessed. Those become "needs human review" flags in the UI.
- **The demo cannot die on stage.** Every successful model or API response is cached. Turn on
  demo mode and the app replays saved results without touching the network.
- **Provider-neutral.** Anthropic API, Groq (free tier), a local model through Ollama (if cloud
  APIs are not allowed), or a fake client for tests and offline rehearsal. Same feature code for all.
- **Measured, not vibes.** `hackkit.evals` scores extraction accuracy per field on labeled cases.

## Quickstart

```bash
make setup                  # venv + install + copy .env.example to .env
source .venv/bin/activate   # once per terminal; make test/demo/run fail with "not found" without it
make demo                   # runs the example feature offline, no key needed
make test                   # full test suite, no network or key needed
make lint                   # ruff check + format check (CI runs the same)
make eval                   # scores every file in evals/cases/ (fake provider by default)
```

Event day? Follow [docs/DAY_OF.md](docs/DAY_OF.md).

To use a real model, set `LLM_PROVIDER=anthropic`, `LLM_MODEL` and `ANTHROPIC_API_KEY` in `.env`,
then `make run`. For Groq, set `LLM_PROVIDER=groq` and `GROQ_API_KEY` (default model
`openai/gpt-oss-120b`). For a local model, install Ollama and set `LLM_PROVIDER=ollama`.

## Add a feature in three steps

```bash
python -m hackkit.scaffold intake_triage "Intake triage"
```

1. Edit the schema in `src/features/intake_triage/__init__.py`. Give each field a description.
2. Write `INSTRUCTIONS` (what to extract) and `rules()` (the deterministic logic).
3. Paste a realistic `sample_text` and `sample_response`, then restart the app. The feature
   appears in the sidebar with upload, results, flags and downloads already working.

`src/features/receipt/` is the reference example: the model lists the items, code adds them up
and flags the receipt when the printed total does not match.

## Calling a sponsor or public API

```python
from hackkit.cache import DiskCache
from hackkit.connector import HttpConnector

api = HttpConnector(
    "https://api.example.com",
    headers={"Authorization": "Bearer ..."},
    cache=DiskCache(".cache/hackkit"),
)
data = api.get_json("/v1/things", params={"q": "bikes"})
```

Timeouts, retries on 5xx and 429, fail-fast on 4xx, caching and demo-mode replay are built in.

## Evals

Add labeled cases to `evals/cases/<feature>.jsonl`:

```json
{"feature": "receipt", "text": "...", "expected": {"merchant": "Corner Market", "tax": 1.34}}
```

`python -m hackkit.evals evals/cases/receipt.jsonl` prints per-field accuracy and writes
`evals/results/latest.md`. Put the table in your final README.

## Layout

```
src/hackkit/      framework: config, llm/, extract, pipeline, feature registry, connector,
                  cache, export, evals, scaffold
src/features/     one package per feature (receipt/ is the example)
app/              Streamlit demo shell
tests/            unit tests and a headless app test (streamlit.testing)
evals/cases/      labeled cases for accuracy checks
CLAUDE.md         instructions for coding agents working in this repo
```

## Hackathon-day runbook

1. Kickoff: listen, talk to the partner, write `docs/spec.md` and the Project section of
   `CLAUDE.md`. Create a new repo from this template.
2. `python -m hackkit.scaffold <name>` and design the schema with real partner vocabulary.
3. Write `rules()` with tests first. This is where correctness lives.
4. Wire the sponsor API through `HttpConnector`.
5. Build the novel feature on top. Only touch `app/` for presentation tweaks.
6. Add 5-10 eval cases and record accuracy.
7. Demo freeze 1h30 before the deadline. Run every demo input once with the real model, then
   switch on demo mode and rehearse.

## Fair-play note

This framework is challenge-agnostic and was published before any event it is used at. All
challenge-specific code is written during the event, in `src/features/` and app tweaks. If an
event's rules restrict prior code, ask the organizers before using it, and disclose it in the
submission either way.

## License

MIT
