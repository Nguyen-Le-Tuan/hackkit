#!/usr/bin/env bash
# Create an isolated worktree + branch for ONE agent, ready to use.
#   scripts/worktree.sh claude   ->  ../<repo>-claude on branch agent/claude
#   scripts/worktree.sh codex    ->  ../<repo>-codex  on branch agent/codex
# Run it from the main checkout after `git merge`-ing the latest work into main.
# Each worktree gets its own .venv (an editable install in a shared venv would import the MAIN
# checkout's code) and a copy of .env (git-ignored files are not shared between worktrees).
set -euo pipefail

name="${1:?usage: scripts/worktree.sh <name>   (e.g. claude, codex)}"
[[ "$name" =~ ^[a-z0-9-]+$ ]] || { echo "name: lowercase letters, digits and dashes only" >&2; exit 2; }

root="$(git rev-parse --show-toplevel)"
dir="$root-$name"
branch="agent/$name"
[[ -e "$dir" ]] && { echo "$dir already exists" >&2; exit 1; }

if git -C "$root" show-ref --verify --quiet "refs/heads/$branch"; then
  git -C "$root" worktree add "$dir" "$branch"
else
  git -C "$root" worktree add -b "$branch" "$dir" HEAD
fi
if [[ -f "$root/.env" && ! -e "$dir/.env" ]]; then cp "$root/.env" "$dir/.env"; fi
(cd "$dir" && make setup >/dev/null)

echo
echo "Ready: $dir (branch $branch). Start your agent there:  cd '$dir' && claude   (or codex)"
echo "Merge it later from the main checkout:  git merge --no-ff $branch"
echo "Remove it when finished:  git worktree remove '$dir' && git branch -d $branch"
