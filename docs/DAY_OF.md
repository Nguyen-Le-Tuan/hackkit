# Event day runbook

Commands only. Fill the placeholders `<...>`. Keep challenge content out of this file.

## Night before
1. `claude`, `codex` and `gh auth status` all work (log in again if not).
2. This template is pushed, its CI is green, and the repo is marked as a template.
3. Keys ready in your password manager (Groq or Anthropic). Never paste them into chat or commits.
4. `./scripts/orchestrate.sh --check --lecturebridge` passes (LectureBridge running).

## At the venue (before you leave the room, ~15 min)
1. Plug in power, check Wi-Fi. Start LectureBridge in terminal 1:
   `cd ~/lecturebridge/lecturebridge && .venv/bin/python -m lecturebridge.live --device cuda --model distil-large-v3.5 --language en`
   Turn on saving of the recording in the browser UI (`http://127.0.0.1:8000`) and put the laptop
   near the speaker. The orchestrator reads the live transcript through the API, so storage
   location does not matter.
2. Create your team repo from this template (private) and clone it:
   `cd ~ && gh repo create <team-repo> --template <owner>/hackkit --private --clone`
3. Invite teammates (they must accept):
   `gh api -X PUT repos/<owner>/<team-repo>/collaborators/<github-user> -f permission=push`
4. Set up: `cd <team-repo> && make setup && source .venv/bin/activate`, put the key in `.env`
   (`LLM_PROVIDER=groq` and `GROQ_API_KEY=...`), then `make test && make lint`.
5. Read the event rules: is pre-existing code allowed, must the template and AI tools be
   disclosed, when is team confirmation due, when do partner reps leave?
6. `./scripts/orchestrate.sh --check --lecturebridge`, and only if it passes:
   `./scripts/orchestrate.sh --at <HH:MM after the briefing> --lock --lecturebridge`
   Close the lid after the lock message (a closed lid muffles the built-in mic; recording that
   matters should happen before it).

## When you are back
1. Unlock. Read `../<team-repo>-agent/docs/agent/STATUS.md`, then `PLAN_REVIEW.md`, then `BRIEF.md`.
   If BRIEF says there is no kickoff content, the wrong audio was captured: re-run once the
   real content is in the transcript.
2. First priority: confirm the team and challenge at the desk and ask the partner the questions in
   `PLANS.md` before the reps leave.
3. Merge the plan docs: `git merge agent/plan`. Choose one plan together (10 min), then fill
   `docs/spec.md`, the Project block in `AGENTS.md` and `docs/TASKS.md` (contract, owners, files).
   Commit and push to `main`.

## Build (parallel agents)
- One agent per person: everyone clones the repo, works on their own branch, never on `main`:
  `git switch -c agent/<name>`, start `claude` or `codex` (both read `AGENTS.md`), and give it
  the task id from `docs/TASKS.md`. Same laptop? Use `scripts/worktree.sh <name>` instead.
- Order: T1 (scaffold + contract) alone first. Merge it. Then parallel tasks whose files do not
  overlap. A reviewer agent reports findings only.
- Open a PR per branch: `git push -u origin agent/<name>` and `gh pr create --base main --fill`.
- The integrator merges only when the PR check is green. If the PR branch is behind `main`, press
  "Update branch" on GitHub or run `git fetch && git merge origin/main && git push`
  ("Re-run jobs" reuses the old merge and will not help). After each merge, `git pull` and run
  `make test && make lint`.
- If `git push` is rejected, someone pushed first: `git pull --rebase origin main`, then push. Never force-push.

## Known traps (learned in rehearsal)
- `make test` says `pytest: not found` -> run `source .venv/bin/activate`.
- `docs/` is excluded from ruff: newer ruff formats code blocks inside Markdown and agent-written
  plans would turn CI red.
- Tests must not assume feature order; a new feature may sort before `receipt` (the app test pins it).
- Fake-provider evals prove the harness only; run a real-model eval before the demo.
- Do not rely on a bot or an agent to merge for you; a human merges after checking CI.

## Freeze and submit
- Demo freeze 1h30 before the deadline: only fixes, rehearse the pitch three times, record a
  backup demo video. Fill `docs/PITCH.md` and submit at least 30 min before the deadline,
  disclosing the template and AI tools.
