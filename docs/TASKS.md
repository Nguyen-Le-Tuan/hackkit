# Tasks (humans edit this file on `main` only; agents read it)

Fill after the plan is chosen (see `docs/agent/PLAN_REVIEW.md`). After every edit (or when a
task's Status changes) run `make lanes`: it rebuilds the "luồng việc hiện tại" block of
`docs/DAY_OF.md` (who works on what, what runs in parallel, who waits for whom, copy-paste commands,
and which milestones are late). Keep every task small (an agent usually needs 5-15 min; the PR,
`make verify`, CI and merge add ~5 min). Two agents may run in parallel ONLY on tasks whose "Files"
do not overlap.

## Team (đội hình: `make lanes` reads this table, keep the three columns)
| Role | Person | Tool |
|------|--------|------|
| claude | <teammate 1> | Claude Code |
| codex | <teammate 2> | Codex |
| human-A | <you> | |
| human-B | <teammate 2> | |
| human-C | <teammate 3> | |
| partner-qa | <teammate 3> | |
| backup-integrator | <teammate 1> | |

Roles: **claude / codex** = the agent that person runs. **human-A** = integrator: reviews PRs with
`make verify PR=N`, merges, owns `docs/TASKS.md`; NOT also the presenter. **human-B** = QA and demo
driver (`make doctor` on the demo laptop). **human-C** = pitch owner FROM MINUTE 0: rubric map,
`make shots` / `make deck` / `make demo-video`, Devpost (`docs/SUBMISSION.md`). **partner-qa** = asks
the partner reps. **backup-integrator** = merges green, verified PRs when human-A is busy, never their
own PR. Change the Person column freely.

## Milestones (`make lanes` warns when one is late: cut scope, never move the milestone)
Fill the real clock times at kickoff (deadline minus the offsets in `docs/pitch/README.md`).

| Milestone | Due (HH:MM) | Done |
|-----------|-------------|------|
| Plan chosen, spec + contract merged | | |
| Ugly end-to-end works and is deployed (`make snapshot`, `make pages`) | | |
| Slides v1 with real screenshots (`make shots && make deck`) | | |
| AI visible in the main demo flow (extract / narrate / ask) | | |
| Freeze (`make freeze`): bug fixes only from here | | |
| Demo video + Devpost page done (`make demo-video`) | | |
| Submitted, confirmation screenshot saved | | |

## Contract (agree and merge this BEFORE parallel work)
The shared interfaces both agents rely on. Nobody changes these without the human's approval.
- Feature key: `<key>` (created with `make feature NAME=<key> TITLE="..." [PAGE=1]`)
- Schema: `<ClassName>` with fields `<field: type>, ...` in `src/features/<key>/__init__.py`
- Money is extracted as `float` exactly as printed (a `Decimal` would serialize to a string and break
  eval matching); `rules()` converts to `Decimal` if it needs exact arithmetic.
- `rules(data) -> RulesResult`: metrics `<...>`, flags `<...>` (every flag reason states both numbers)
- Shown values carry their source (`hackkit.provenance`); made-up values use source `demo` (red).
- Partner worked examples, if any: golden tests (`hackkit.golden`); confidential files stay in `partner/`.
- Sample files: `<path>`; eval cases: `evals/cases/<key>.jsonl` (each case has its own `fake_response`;
  the eval scores TOP-LEVEL fields only, so line-level logic is verified by unit tests)

## Tasks
Columns used by `make lanes`: **Owner** starts with a role from the Team table. **Depends on**: `T1`
= hard dependency (cannot start before T1 is merged; a review task `R*` only needs its target
pushed for review). `T1~` = soft dependency (can start now, can only finish after T1 is merged).
**Status**: `todo` | `doing` | `review` (PR open) | `merged` | `blocked`.

| ID | Task | Owner | Files it may touch | Depends on | Status |
|----|------|-------|--------------------|------------|--------|
| T0 | Pitch kit from minute 0: `make init-project`, rubric map + timeline in `docs/pitch/README.md`, deck v0 (titles only), find ONE sourced impact number | human-C | `web/config.json`, `docs/pitch/`, `docs/SUBMISSION.md`, `README.md` | - | todo |
| T1 | Registered feature skeleton: `make feature NAME=<key>`, schema, instructions, sample text and response, stub `rules()` (this becomes the Contract; open the PR within ~10 min) | claude | `src/features/<key>/`, `tests/test_<key>.py`, `evals/cases/<key>.jsonl` | - | todo |
| T2 | `rules()` + unit tests for the checks listed in `docs/spec.md` (+ golden tests if the partner gave a worked example) | claude | `src/features/<key>/__init__.py`, `tests/test_<key>.py` | T1 | todo |
| T3 | Synthetic data + 3 labeled eval cases, then `make eval` | codex | `evals/cases/<key>.jsonl`, `data/synthetic/` | T1~ | todo |
| T4 | Visible AI in the demo flow: `narrative` (Explain button) or an `ask` route + page | codex | `src/features/<key>/`, `web/js/pages/` | T2 | todo |
| R1 | Review T2's branch, report findings only, no edits | codex | | T2 | todo |
| T5 | Demo QA on the demo laptop: `make doctor`, `#/doctor`, `make snapshot` with the real model, `make web` offline, rehearse 3 times | human-B | (none; report defects) | T2, T3 | todo |
| T6 | Slides v1 + script + video: `make shots && make deck && make demo-video`; Devpost text discloses the template and AI tools | human-C | `docs/pitch/`, `docs/SUBMISSION.md`, `README.md` | T0, T2 | todo |

## Requests (an agent needs a change in a file it does not own)
- (none yet)

## Merge log (human appends after each merge)
- (none yet)
