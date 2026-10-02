# Tasks (humans edit this file on `main` only; agents read it)

Fill after the plan is chosen (see `docs/agent/PLAN_REVIEW.md`). Keep every task under ~30 min.
Two agents may run in parallel ONLY on tasks whose "Files" do not overlap.

## Contract (agree and merge this BEFORE parallel work)
The shared interfaces both agents rely on. Nobody changes these without the human's approval.
- Feature key: `<key>`
- Schema: `<ClassName>` with fields `<field: type>, ...` in `src/features/<key>/__init__.py`
- `rules(data) -> RulesResult`: metrics `<...>`, flags `<...>`
- Sample files: `<path>`; eval cases: `evals/cases/<key>.jsonl`

## Tasks
| ID | Task (<=30 min) | Owner (human / claude / codex) | Files it may touch | Depends on | Status |
|----|-----------------|--------------------------------|--------------------|------------|--------|
| T1 | Scaffold feature + schema + sample text (this becomes the Contract) | | `src/features/<key>/` | - | todo |
| T2 | `rules()` + unit tests | | `src/features/<key>/`, `tests/test_<key>.py` | T1 | todo |
| T3 | Synthetic sample data + 3 eval cases | | `evals/cases/<key>.jsonl`, `data/synthetic/` | T1 | todo |
| T4 | UI tweaks for the demo flow | | `app/` | T1 | todo |
| T5 | Demo script, pitch, Devpost text | | `docs/PITCH.md`, `README.md` | T2 | todo |

Status values: `todo` | `doing` | `review` | `merged` | `blocked`.

## Requests (an agent needs a change in a file it does not own)
- <date/time> <agent>: <file> <what is needed and why>

## Merge log (human appends after each merge)
- <time> merged `agent/<name>` (<task ids>); `make test` and `make lint` pass: yes/no
