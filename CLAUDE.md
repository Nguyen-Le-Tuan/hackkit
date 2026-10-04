# CLAUDE.md

@AGENTS.md

## Claude Code specifics
- Shared permissions are in `.claude/settings.json` (tests, lint, make and read-only git are
  pre-approved; `.env` is unreadable; `git push` asks first). Personal overrides go in
  `.claude/settings.local.json`, which is git-ignored.
- Use plan mode for any change over ~50 lines, as AGENTS.md requires.
- Planning documents from the kickoff run live in `docs/agent/` (BRIEF, PLANS, PLAN_REVIEW).
  They are proposals; the human-approved decisions are in `docs/spec.md`.
- UI work: open the app (`make run`) and check `#/kit` for components before writing new CSS; verify
  with `python scripts/shots.py --smoke` and look at the screenshot from `make shots ONLY=<name>`.
