# Tasks (humans edit this file on `main` only; agents read it)

Fill after the plan is chosen (see `docs/agent/PLAN_REVIEW.md`). After every edit (or when a
task's Status changes) run `make lanes`: it rebuilds the "luồng việc hiện tại" block of
`docs/DAY_OF.md` (who works on what, what runs in parallel, who waits for whom, copy-paste commands).
Keep every task small (an agent usually needs 5-15 min; the PR, CI and merge add ~5 min).
Two agents may run in parallel ONLY on tasks whose "Files" do not overlap.

## Team (đội hình: `make lanes` reads this table, keep the three columns)
| Role | Person | Tool |
|------|--------|------|
| claude | Anh-08 | Claude Code |
| codex | NguyenQBao | Codex |
| human-A | Nguyen-Le-Tuan (tôi) | |
| human-B | NguyenQBao | |
| human-C | Anh-08 | |
| partner-qa | NguyenQBao | |
| backup-integrator | Anh-08 | |

Roles: **claude / codex** = the agent that person runs. **human-A** = product owner, partner
questions, integrator (reviews PRs, merges, runs `make test && make lint`). **human-B** = QA and demo
driver. **human-C** = pitch and Devpost. **partner-qa** = asks the partner reps (while human-A reviews
BRIEF and decides). **backup-integrator** = merges green PRs when human-A is busy, never their own PR.
Change the Person column freely.

## Contract (agree and merge this BEFORE parallel work)
The shared interfaces both agents rely on. Nobody changes these without the human's approval.
- Feature key: `<key>`
- Schema: `<ClassName>` with fields `<field: type>, ...` in `src/features/<key>/__init__.py`
- Money is extracted as `float` exactly as printed (a `Decimal` would serialize to a string and break
  eval matching); `rules()` converts to `Decimal` if it needs exact arithmetic.
- `rules(data) -> RulesResult`: metrics `<...>`, flags `<...>` (every flag reason states both numbers)
- Sample files: `<path>`; eval cases: `evals/cases/<key>.jsonl` (each case has its own `fake_response`;
  the eval scores TOP-LEVEL fields only, so line-level logic is verified by unit tests)

## Tasks
Columns used by `make lanes`: **Owner** starts with a role from the Team table. **Depends on**: `T1`
= hard dependency (cannot start before T1 is merged; a review task `R*` only needs its target
pushed for review). `T1~` = soft dependency (can start now, can only finish after T1 is merged).
**Status**: `todo` | `doing` | `review` (PR open) | `merged` | `blocked`.

| ID | Task | Owner | Files it may touch | Depends on | Status |
|----|------|-------|--------------------|------------|--------|
| T1 | Registered feature skeleton: schema, instructions, sample text and response, stub `rules()` (this becomes the Contract; open the PR within ~10 min) | claude | `src/features/<key>/` | - | todo |
| T2 | `rules()` + unit tests for the checks listed in `docs/spec.md` | claude | `src/features/<key>/__init__.py`, `tests/test_<key>.py` | T1 | todo |
| T3 | Synthetic data + 3 labeled eval cases, then `make eval` | codex | `evals/cases/<key>.jsonl`, `data/synthetic/` | T1~ | todo |
| R1 | Review T2's branch, report findings only, no edits | codex | | T2 | todo |
| T4 | Verify the demo flow: flags, summary, export, `make test`, `make lint`, `make demo`; rehearse 3 times | human-B | `app/` (only if a defect is found; ask first) | T2, T3 | todo |
| T5 | Pitch outline, demo script and Devpost text from `docs/PITCH.md`; disclose the template and AI tools | human-C | `docs/PITCH.md`, `README.md` | T1 | todo |

## Requests (an agent needs a change in a file it does not own)
- (none yet)

## Merge log (human appends after each merge)
- (none yet)
