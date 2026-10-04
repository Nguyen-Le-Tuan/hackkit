#!/usr/bin/env bash
# orchestrate.sh - Claude Code + Codex planning relay (v3: unattended and self-healing).
# Agents PREPARE the plan from the kickoff transcript. Humans DECIDE.
#
# Usage (pick exactly ONE transcript source: --lecturebridge OR --transcript):
#   ./scripts/orchestrate.sh --check --lecturebridge                  # preflight only, ~1 min
#   ./scripts/orchestrate.sh --at 11:00 --lock --lecturebridge        # event day
#   ./scripts/orchestrate.sh --now --lecturebridge                    # run immediately
#   ./scripts/orchestrate.sh --at 11:00 --lock --transcript '<file-or-glob>'
#   ./scripts/orchestrate.sh --now --transcript ./fake_transcript.txt # rehearsal with a plain file
#
# --lecturebridge: reads the LIVE transcript of the newest recording whose status is
#   "recording" through the LectureBridge HTTP API (default http://127.0.0.1:8000, override with
#   --lecturebridge-url URL). The recording is NOT stopped, no file is created next to it, and
#   library.sqlite3 is never touched. A finished ("complete"/"interrupted") session is never used.
# --transcript: a file or a quoted glob; the NEWEST match is used.
# Either way the transcript is copied at exactly --at HH:MM (default 11:00), even if the
# recorder keeps appending to it afterwards.
# --document: the --transcript file is a WRITTEN document (e.g. a handout converted to text), not speech.
# --with-file PATH (repeatable): prepend written documents to the snapshot, e.g. the problem statement
#   together with a live recording of the grading/pitch briefing:
#     ./scripts/orchestrate.sh --now --lecturebridge --with-file docs/<problem-statement>.txt
# --chosen "TEXT": the team has already picked its challenge; the plan then focuses on it.
#   Previous BRIEF/CRITIQUE/PLANS/PLAN_REVIEW are archived in docs/agent/archive/<time>/ before a re-run.
# --snapshot-only (testing): wait, take the snapshot, print the temp file path, exit. No agents,
#   no lid guard, no lock.
# Secrets: the agents run in a worktree NEXT TO the repo and can read ../.env. A real run therefore
#   refuses to start while .env holds filled-in keys (override: --allow-secrets), and after the
#   run every changed file is scanned for key values (see the 'Secret scan' block in STATUS.md).
#   Keep API keys out of .env until the run has finished.
#
# Self-healing: every step is tried up to 3 times (agent, agent again, then Claude Opus with
# high effort). If Codex is unusable, its steps go straight to Claude Opus.
# Lid guard: while running, closing the lid does not suspend the laptop (GNOME lid actions are
# set to "nothing" and restored on exit; see LID_STATE if the script is killed with SIGKILL).
#
# Stop at any time:  touch "$REPO_DIR/STOP"  (checked before each step), or Ctrl-C.
# Read on return:    "$REPO_DIR-agent/docs/agent/STATUS.md", then PLAN_REVIEW.md, then BRIEF.md

set -uo pipefail

# ---------------- CONFIG (edit or override with env vars) ----------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
REPO_DIR="${REPO_DIR:-$(dirname "$SCRIPT_DIR")}"       # default: the repo this script lives in
TRANSCRIPT_PATH="${TRANSCRIPT_PATH:-}"                 # file or glob (required)
RUN_AT="${RUN_AT:-11:00}"                              # HH:MM, 24h, same day
BRANCH="${BRANCH:-agent/plan}"
WT_DIR="${WT_DIR:-${REPO_DIR}-agent}"                  # git worktree for the agents
TRANSCRIPT_WAIT_MIN="${TRANSCRIPT_WAIT_MIN:-20}"       # how long to wait for the transcript
TRANSCRIPT_WAIT_S="${TRANSCRIPT_WAIT_S:-$((TRANSCRIPT_WAIT_MIN * 60))}"
TRANSCRIPT_POLL_S="${TRANSCRIPT_POLL_S:-10}"           # seconds between retries
LB_URL="${LECTUREBRIDGE_URL:-http://127.0.0.1:8000}"   # used with --lecturebridge
CLAUDE_TOOLS="Read,Write,Edit,Glob,Grep"               # planning only: no shell commands
CLAUDE_BIN="${CLAUDE_BIN:-claude}"
CODEX_BIN="${CODEX_BIN:-codex}"
FALLBACK_MODEL="${FALLBACK_MODEL:-claude-opus-5-5}"    # used when the primary agent fails
FALLBACK_EFFORT="${FALLBACK_EFFORT:-high}"
FALLBACK_MINS="${FALLBACK_MINS:-15}"
RETRY_PAUSE="${RETRY_PAUSE:-20}"                       # seconds, multiplied by the try number
LID_STATE="${LID_STATE:-$HOME/.cache/orchestrate_lid_restore.sh}"
# --------------------------------------------------------------------------

RUN_NOW=0 LOCK=0 CHECK=0 LID_GUARD=1 LB_MODE=0 LB_URL_SET=0 SNAPSHOT_ONLY=0 ALLOW_SECRETS=0 DOC_MODE=0
WITH_FILES=()
CHOSEN="${CHOSEN:-}"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --now) RUN_NOW=1; shift ;;
    --at) RUN_AT="$2"; shift 2 ;;
    --transcript) TRANSCRIPT_PATH="$2"; shift 2 ;;
    --lecturebridge) LB_MODE=1; shift ;;
    --lecturebridge-url) LB_URL="$2"; LB_URL_SET=1; shift 2 ;;
    --lock) LOCK=1; shift ;;
    --check) CHECK=1; shift ;;
    --snapshot-only) SNAPSHOT_ONLY=1; shift ;;
    --no-lid-guard) LID_GUARD=0; shift ;;
    --allow-secrets) ALLOW_SECRETS=1; shift ;;
    --document) DOC_MODE=1; shift ;;
    --with-file) WITH_FILES+=("$2"); shift 2 ;;
    --chosen) CHOSEN="$2"; shift 2 ;;
    *) echo "Unknown argument: $1"; exit 2 ;;
  esac
done
[[ "$RUN_AT" =~ ^([01][0-9]|2[0-3]):[0-5][0-9]$ ]] || { echo "--at must be HH:MM (24h)"; exit 2; }
if [[ $LB_MODE -eq 1 && -n "$TRANSCRIPT_PATH" ]]; then
  echo "--lecturebridge and --transcript (or TRANSCRIPT_PATH) are mutually exclusive: use one."
  exit 2
fi
if [[ $LB_MODE -eq 0 && $LB_URL_SET -eq 1 ]]; then
  echo "--lecturebridge-url only makes sense together with --lecturebridge."
  exit 2
fi
if [[ $CHECK -eq 0 && $LB_MODE -eq 0 && -z "$TRANSCRIPT_PATH" ]]; then
  echo "Pick a transcript source: --lecturebridge, or --transcript '<file-or-glob>'"
  echo "(no default: a wrong guess could pick a stale file)."
  exit 2
fi
if [[ $LB_MODE -eq 1 ]]; then
  LB_URL="${LB_URL%/}"
  [[ "$LB_URL" =~ ^https?://[^[:space:]]+$ ]] || { echo "--lecturebridge-url must look like http://127.0.0.1:8000"; exit 2; }
fi
if [[ $DOC_MODE -eq 1 && $LB_MODE -eq 1 ]]; then echo "--document applies to --transcript files, not --lecturebridge."; exit 2; fi
if [[ ${#CHOSEN} -gt 300 ]]; then echo "--chosen is limited to 300 characters."; exit 2; fi
for i in "${!WITH_FILES[@]}"; do
  f="${WITH_FILES[$i]/#\~/$HOME}"; [[ "$f" == /* ]] || f="$PWD/$f"
  [[ -s "$f" ]] || { echo "--with-file: not found or empty: $f"; exit 2; }
  WITH_FILES[i]="$f"
done
TRANSCRIPT_PATH="${TRANSCRIPT_PATH/#\~/$HOME}"
[[ -z "$TRANSCRIPT_PATH" || "$TRANSCRIPT_PATH" == /* ]] || TRANSCRIPT_PATH="$PWD/$TRANSCRIPT_PATH"
if [[ $SNAPSHOT_ONLY -eq 1 ]]; then LID_GUARD=0; LOCK=0; fi

# Keep the machine awake for the whole run (screen may lock and the lid may be closed).
ARGS=(--at "$RUN_AT")
if [[ $LB_MODE -eq 1 ]]; then ARGS+=(--lecturebridge --lecturebridge-url "$LB_URL")
else ARGS+=(--transcript "$TRANSCRIPT_PATH"); fi
[[ $SNAPSHOT_ONLY -eq 1 ]] && ARGS+=(--snapshot-only)
[[ $RUN_NOW -eq 1 ]] && ARGS+=(--now)
[[ $LOCK -eq 1 ]] && ARGS+=(--lock)
[[ $CHECK -eq 1 ]] && ARGS+=(--check)
[[ $LID_GUARD -eq 0 ]] && ARGS+=(--no-lid-guard)
[[ $ALLOW_SECRETS -eq 1 ]] && ARGS+=(--allow-secrets)
[[ $DOC_MODE -eq 1 ]] && ARGS+=(--document)
for f in "${WITH_FILES[@]}"; do ARGS+=(--with-file "$f"); done
[[ -n "$CHOSEN" ]] && ARGS+=(--chosen "$CHOSEN")
if [[ -z "${AWAKE:-}" ]]; then
  export AWAKE=1
  if [[ "$(uname)" == "Darwin" ]] && command -v caffeinate >/dev/null; then
    exec caffeinate -i "$0" "${ARGS[@]}"
  elif command -v systemd-inhibit >/dev/null &&
    systemd-inhibit --what=idle:sleep:handle-lid-switch --why=check true >/dev/null 2>&1; then
    exec systemd-inhibit --what=idle:sleep:handle-lid-switch --why="hackathon agent run" "$0" "${ARGS[@]}"
  else
    echo "WARNING: could not block sleep. Disable suspend in Settings > Power for the run."
  fi
fi

DOCS_DIR="$WT_DIR/docs/agent"
LOG_DIR="$DOCS_DIR/logs"
STATUS="$DOCS_DIR/STATUS.md"
NOTES="$(mktemp)"                                      # preflight notes, copied into STATUS later

log() { echo "[$(date +%H:%M:%S)] $*" | tee -a "$STATUS" 2>/dev/null || echo "[$(date +%H:%M:%S)] $*"; }
note() { echo "$*"; echo "- $*" >>"$NOTES"; }
die() { echo "ERROR: $*" >&2; [[ -f "$STATUS" ]] && echo "- ERROR: $*" >>"$STATUS"; exit 1; }
check_stop() { [[ -f "$REPO_DIR/STOP" ]] && { log "STOP file found, exiting."; exit 0; }; return 0; }

if command -v timeout >/dev/null; then TO=timeout
elif command -v gtimeout >/dev/null; then TO=gtimeout
else TO=""; fi
with_timeout() { local mins=$1; shift; if [[ -n "$TO" ]]; then "$TO" "${mins}m" "$@"; else "$@"; fi; }

# Newest non-empty file matching TRANSCRIPT_PATH (a plain path also works).
latest_transcript() {
  local f best=""
  while IFS= read -r f; do
    [[ -f "$f" && -s "$f" ]] || continue
    if [[ -z "$best" || "$f" -nt "$best" ]]; then best="$f"; fi
  done < <(compgen -G "$TRANSCRIPT_PATH")
  [[ -n "$best" ]] && printf '%s\n' "$best"
}

# ---------------- PREFLIGHT ----------------
CODEX_OK=1
smoke_ok() { # exit-code output
  [[ $1 -eq 0 ]] && grep -qE '^OK\.?$' <<<"$2"
}
smoke_claude() { # extra claude args...
  local out rc
  out="$(cd /tmp && with_timeout 3 "$CLAUDE_BIN" -p "Reply with the single word OK" --max-turns 1 "$@" 2>&1)"; rc=$?
  smoke_ok $rc "$out"
}
smoke_codex() {
  local out rc
  out="$(cd /tmp && with_timeout 3 "$CODEX_BIN" exec --skip-git-repo-check "Reply with the single word OK" 2>&1)"; rc=$?
  smoke_ok $rc "$out"
}

preflight_env() {
  local cmd p
  note "Repo: $REPO_DIR (agent worktree: $WT_DIR, branch $BRANCH)"
  if [[ ! -x "$0" ]]; then
    if chmod +x "$0" 2>/dev/null; then note "FIXED: $0 was not executable (chmod +x applied)."
    else note "WARN: $0 is not executable; start it with: bash $0 ..."; fi
  fi
  for cmd in "$CLAUDE_BIN" git; do
    p="$(command -v "$cmd")" && [[ -x "$p" ]] || die "missing or not executable: $cmd"
  done
  p="$(command -v "$CODEX_BIN")" && [[ -x "$p" ]] || { CODEX_OK=0; note "WARN: $CODEX_BIN missing or not executable; Codex steps will run on Claude Opus."; }
  git -C "$REPO_DIR" rev-parse --is-inside-work-tree >/dev/null 2>&1 || die "REPO_DIR is not a git repo: $REPO_DIR"
  [[ -f "$REPO_DIR/CLAUDE.md" ]] || die "CLAUDE.md not found in $REPO_DIR"
  [[ -f "$REPO_DIR/STOP" ]] && die "Remove $REPO_DIR/STOP before starting."
  [[ -z "$TO" ]] && note "WARN: no 'timeout' command. Steps will not be time-boxed."
  if [[ -f "$REPO_DIR/.env" ]]; then
    filled="$(python3 "$SCRIPT_DIR/secret_scan.py" --check-env --env "$REPO_DIR/.env" 2>&1)" && rc=0 || rc=$?
    if [[ $rc -eq 0 ]]; then
      note "OK: $REPO_DIR/.env holds no filled-in secret values."
    else
      names="$(tr '\n' ' ' <<<"$filled")"
      msg=".env holds filled-in keys ($names). The agents can read ../.env. Remove the keys until the run is done."
      if [[ $CHECK -eq 1 || $ALLOW_SECRETS -eq 1 ]]; then note "WARN: $msg"; else die "$msg (override: --allow-secrets)"; fi
    fi
  fi

  echo "Smoke-testing agents (a few seconds each) ..."
  smoke_claude || { sleep 3; smoke_claude; } || die "Claude (default model) failed the smoke test. Run '$CLAUDE_BIN' once and log in / fix it."
  note "OK: Claude (default model) answers."
  smoke_claude --model "$FALLBACK_MODEL" --effort "$FALLBACK_EFFORT" ||
    smoke_claude --model "$FALLBACK_MODEL" --effort "$FALLBACK_EFFORT" ||
    die "Fallback $FALLBACK_MODEL (effort $FALLBACK_EFFORT) failed the smoke test."
  note "OK: fallback $FALLBACK_MODEL (effort $FALLBACK_EFFORT) answers."
  if [[ $CODEX_OK -eq 1 ]]; then
    if smoke_codex || { sleep 3; smoke_codex; }; then note "OK: Codex answers."
    else CODEX_OK=0; note "WARN: Codex failed the smoke test (login/version/model?). Its steps will run on Claude Opus."; fi
  fi

}

# ---- LectureBridge live source (HTTP API only; never reads library.sqlite3) ----
lb_get() { curl -fsS --max-time 15 "$LB_URL$1"; }   # LB_URL is validated as http(s)://...

# Id of the NEWEST recording whose status is exactly "recording"; nothing printed if none.
lb_recording_id() {
  local id
  id="$(lb_get /api/recordings 2>/dev/null | jq -r '
    if type == "array"
    then ([.[] | select(.status == "recording")] | sort_by(.created) | reverse | .[0].id // empty)
    else empty end' 2>/dev/null)" || return 1
  [[ "$id" =~ ^[0-9a-fA-F-]{36}$ ]] || return 1
  printf '%s\n' "$id"
}

# Writes the live transcript of the recording session into $SNAP_TMP. Sets LB_ID on success.
LB_ID=""
lb_fetch_snapshot() {
  local id
  id="$(lb_recording_id)" || return 1
  lb_get "/api/recordings/$id/export?format=txt" >"$SNAP_TMP" 2>/dev/null || return 1
  grep -q '[^[:space:]]' "$SNAP_TMP" || return 1      # reject empty / whitespace-only
  LB_ID="$id"
}

preflight_source() {
  local p id n cmd
  if [[ $LB_MODE -eq 1 ]]; then
    for cmd in curl jq; do
      command -v "$cmd" >/dev/null || die "missing command for --lecturebridge: $cmd"
    done
    n=""
    for _ in 1 2 3; do                                  # tolerate a transient error
      n="$(lb_get /api/recordings 2>/dev/null | jq -e 'type == "array"' 2>/dev/null)" && [[ "$n" == true ]] && break
      n=""; sleep 2
    done
    [[ -n "$n" ]] ||
      die "LectureBridge API not reachable (or unexpected reply) at $LB_URL/api/recordings. Start LectureBridge first."
    note "OK: LectureBridge API reachable at $LB_URL."
    if id="$(lb_recording_id)"; then
      n="$(lb_get "/api/recordings/$id/export?format=txt" 2>/dev/null | wc -c)"
      note "OK: a recording session is active (id $id, transcript so far: $n bytes)."
    else
      note "No session with status=recording yet; the script will wait for one until the snapshot time."
    fi
  elif [[ -n "$TRANSCRIPT_PATH" ]]; then
    p="$(latest_transcript)" && note "Transcript match now: $p ($(stat -c %s "$p") bytes)." ||
      note "Transcript: no non-empty match yet for $TRANSCRIPT_PATH (will wait until the snapshot time)."
  fi
}

# ---------------- LID GUARD ----------------
GS_SCHEMA=org.gnome.settings-daemon.plugins.power
lid_guard_on() {
  command -v gsettings >/dev/null || { note "WARN: no gsettings; lid close may still suspend."; return 0; }
  local ac bat
  ac="$(gsettings get $GS_SCHEMA lid-close-ac-action 2>/dev/null)" &&
    bat="$(gsettings get $GS_SCHEMA lid-close-battery-action 2>/dev/null)" ||
    { note "WARN: GNOME lid settings not found; lid close may still suspend."; return 0; }
  if [[ ! -f "$LID_STATE" ]]; then   # keep the ORIGINAL values if a previous run crashed
    mkdir -p "$(dirname "$LID_STATE")"
    printf 'gsettings set %s lid-close-ac-action %s\ngsettings set %s lid-close-battery-action %s\nrm -f "%s"\n' \
      "$GS_SCHEMA" "$ac" "$GS_SCHEMA" "$bat" "$LID_STATE" >"$LID_STATE"
  fi
  gsettings set $GS_SCHEMA lid-close-ac-action nothing
  gsettings set $GS_SCHEMA lid-close-battery-action nothing
  note "Lid guard ON: closing the lid will not suspend (was ac=$ac, battery=$bat; restored on exit)."
}
lid_guard_off() { [[ -f "$LID_STATE" ]] && bash "$LID_STATE"; return 0; }

if [[ $SNAPSHOT_ONLY -eq 1 ]]; then preflight_source; else preflight_env; preflight_source; fi
if [[ $CHECK -eq 1 ]]; then
  echo; echo "Preflight finished. Codex usable: $CODEX_OK. Nothing was started."
  [[ $CODEX_OK -eq 1 ]] || echo "(Codex steps would fall back to $FALLBACK_MODEL.)"
  rm -f "$NOTES"; exit 0
fi

if [[ $LID_GUARD -eq 1 ]]; then
  trap 'lid_guard_off' EXIT
  lid_guard_on
fi
if [[ $LOCK -eq 1 ]]; then
  note "Locking the session in 10 s (loginctl lock-session). Close the lid after that."
  sleep 10
  loginctl lock-session || note "WARN: loginctl lock-session failed; lock the screen yourself."
fi

echo "Repo:       $REPO_DIR"
if [[ $LB_MODE -eq 1 ]]; then echo "Transcript: LectureBridge live API at $LB_URL"
else echo "Transcript: $TRANSCRIPT_PATH"; fi
echo "Worktree:   $WT_DIR (branch $BRANCH)"

# ---------------- WAIT, THEN SNAPSHOT AT THE EXACT TIME ----------------
if [[ $RUN_NOW -eq 0 ]]; then
  echo "Waiting until $RUN_AT ... (touch $REPO_DIR/STOP to cancel)"
  TARGET="$(date -d "today $RUN_AT" +%s)"
  while (( $(date +%s) < TARGET )); do
    check_stop
    left=$(( TARGET - $(date +%s) ))
    sleep $(( left > 30 ? 30 : (left > 0 ? left : 1) ))
  done
fi

SNAP_TIME="$(date +%H:%M:%S)"
SNAP_TMP="$(mktemp)"
SRC=""
if [[ $LB_MODE -eq 1 ]]; then
  # Retry while there is no status=recording session, the API hiccups, or the transcript is empty.
  for ((waited = 0; waited < TRANSCRIPT_WAIT_S; waited += TRANSCRIPT_POLL_S)); do
    lb_fetch_snapshot && break
    check_stop; sleep "$TRANSCRIPT_POLL_S"
  done
  [[ -n "$LB_ID" ]] || { rm -f "$SNAP_TMP"; die "no LectureBridge session with status=recording and a non-empty transcript at $LB_URL after ${TRANSCRIPT_WAIT_S}s"; }
else
  for ((waited = 0; waited < TRANSCRIPT_WAIT_S; waited += TRANSCRIPT_POLL_S)); do
    SRC="$(latest_transcript)" && break
    SRC=""; check_stop; sleep "$TRANSCRIPT_POLL_S"
  done
  [[ -n "$SRC" ]] || { rm -f "$SNAP_TMP"; die "no non-empty transcript matches: $TRANSCRIPT_PATH"; }
  cp -- "$SRC" "$SNAP_TMP" || die "cannot copy transcript $SRC"
  SRC_MTIME="$(date -d "@$(stat -c %Y "$SRC")" +%H:%M:%S)"
fi
# Several sources (or a written document): label each source so the agents know what they are reading.
if [[ ${#WITH_FILES[@]} -gt 0 || $DOC_MODE -eq 1 ]]; then
  COMPOSED="$(mktemp)"
  for f in "${WITH_FILES[@]}"; do
    { echo "===== DOCUMENT (written, converted to text): $(basename "$f") ====="; cat -- "$f"; echo; } >>"$COMPOSED"
  done
  if [[ $LB_MODE -eq 1 ]]; then echo "===== LIVE TRANSCRIPT (speech-to-text of the room, via LectureBridge) =====" >>"$COMPOSED"
  elif [[ $DOC_MODE -eq 1 ]]; then echo "===== DOCUMENT (written, converted to text): $(basename "$SRC") =====" >>"$COMPOSED"
  else echo "===== TRANSCRIPT: $(basename "$SRC") =====" >>"$COMPOSED"; fi
  cat -- "$SNAP_TMP" >>"$COMPOSED"; mv -- "$COMPOSED" "$SNAP_TMP"
fi
SNAP_DONE="$(date +%H:%M:%S)"
SRC_BYTES="$(stat -c %s "$SNAP_TMP")"
if [[ $SNAPSHOT_ONLY -eq 1 ]]; then
  echo "SNAPSHOT_FILE=$SNAP_TMP"
  echo "SNAPSHOT_SOURCE=$([[ $LB_MODE -eq 1 ]] && echo "lecturebridge:$LB_ID" || echo "file:$SRC")"
  echo "SNAPSHOT_BYTES=$SRC_BYTES"
  rm -f "$NOTES"
  exit 0
fi

# ---------------- WORKTREE ----------------
cd "$REPO_DIR" || die "cannot cd to $REPO_DIR"
if [[ ! -d "$WT_DIR" ]]; then
  if git show-ref --verify --quiet "refs/heads/$BRANCH"; then
    git worktree add "$WT_DIR" "$BRANCH" || die "git worktree add failed"
  else
    git worktree add -b "$BRANCH" "$WT_DIR" HEAD || die "git worktree add failed"
  fi
fi
mkdir -p "$LOG_DIR"

# Never commit the transcript (other people's voices) or raw logs.
EXCLUDE_FILE="$(git rev-parse --git-common-dir)/info/exclude"
mkdir -p "$(dirname "$EXCLUDE_FILE")"
for pattern in "docs/agent/transcript_snapshot.txt" "docs/agent/logs/"; do
  grep -qxF "$pattern" "$EXCLUDE_FILE" 2>/dev/null || echo "$pattern" >>"$EXCLUDE_FILE"
done

START_SHA="$(git -C "$WT_DIR" rev-parse HEAD)"
# A reused worktree may hold outputs of an older run: a stale file must never pass for a new one.
if compgen -G "$DOCS_DIR/BRIEF.md" >/dev/null; then   # keep the previous run's outputs
  ARCH="$DOCS_DIR/archive/$(date +%Y%m%d-%H%M%S)"; mkdir -p "$ARCH"
  for f in BRIEF CRITIQUE PLANS PLAN_REVIEW; do [[ -f "$DOCS_DIR/$f.md" ]] && cp -- "$DOCS_DIR/$f.md" "$ARCH/"; done
fi
rm -f "$DOCS_DIR"/{BRIEF,CRITIQUE,PLANS,PLAN_REVIEW}.md
mv -- "$SNAP_TMP" "$DOCS_DIR/transcript_snapshot.txt"
{
  echo "# Agent run status"; echo
  [[ $DOC_MODE -eq 1 ]] && echo "Source kind: written document (not speech)."
  for f in "${WITH_FILES[@]}"; do echo "Extra document: \`$(basename "$f")\` ($(stat -c %s "$f") bytes)."; done
  [[ -n "$CHOSEN" ]] && echo "Chosen challenge (given by the human): $CHOSEN"
  echo "Started $(date '+%Y-%m-%d %H:%M')."
  if [[ $LB_MODE -eq 1 ]]; then
    echo "Transcript source: LectureBridge API (live, recording not stopped)."
    echo "- API URL: \`$LB_URL\`"
    echo "- Recording ID: \`$LB_ID\`"
    echo "- Snapshot: $SRC_BYTES bytes, taken $SNAP_TIME-$SNAP_DONE (target $RUN_AT). Content is not logged here."
  else
    echo "Transcript: \`$SRC\` ($SRC_BYTES bytes), copied $SNAP_TIME-$SNAP_DONE (target $RUN_AT); file last modified $SRC_MTIME."
  fi
  echo; echo "## Preflight"; cat "$NOTES"; echo
} >"$STATUS"
rm -f "$NOTES"

checkpoint() { (cd "$WT_DIR" && git add -A && git commit -qm "agent: $1" --no-verify) >/dev/null 2>&1 || true; }

# ---------------- RUNNERS ----------------
claude_run() { # logname mins turns prompt [extra claude args...]
  local logname=$1 mins=$2 turns=$3 prompt=$4; shift 4
  (cd "$WT_DIR" && with_timeout "$mins" "$CLAUDE_BIN" -p "$prompt" \
      --allowedTools "$CLAUDE_TOOLS" --permission-mode acceptEdits --max-turns "$turns" "$@") \
      >"$LOG_DIR/$logname.out" 2>"$LOG_DIR/$logname.err"
}
codex_run() { # logname mins prompt
  local logname=$1 mins=$2 prompt=$3
  (cd "$WT_DIR" && with_timeout "$mins" "$CODEX_BIN" exec --sandbox workspace-write -C "$WT_DIR" "$prompt") \
      >"$LOG_DIR/$logname.out" 2>"$LOG_DIR/$logname.err"
}
agent_label() {
  case "$1" in
    claude) echo "Claude" ;;
    fallback) echo "Claude Opus: $FALLBACK_MODEL, effort $FALLBACK_EFFORT" ;;
    codex) echo "Codex" ;;
  esac
}

# run_step <name> <claude|codex> <minutes> <turns> <expected file> <prompt>
# Tries primary, primary again, then Claude Opus. Success = exit 0 AND the expected file exists.
run_step() {
  local name=$1 primary=$2 mins=$3 turns=$4 want=$5 prompt=$6
  local -a plan; local n=0 agent rc start
  if [[ $primary == codex && $CODEX_OK -eq 0 ]]; then plan=(fallback fallback)
  else plan=("$primary" "$primary" fallback); fi
  for agent in "${plan[@]}"; do
    n=$((n + 1)); check_stop
    rm -f "$DOCS_DIR/$want"
    log "START $name try $n/${#plan[@]} ($(agent_label "$agent"))"
    start=$SECONDS
    case "$agent" in
      claude) claude_run "$name.try$n" "$mins" "$turns" "$prompt" ;;
      fallback) claude_run "$name.try$n" "$FALLBACK_MINS" "$turns" "$prompt" \
                  --model "$FALLBACK_MODEL" --effort "$FALLBACK_EFFORT" ;;
      codex) codex_run "$name.try$n" "$mins" "$prompt" ;;
    esac
    rc=$?
    log "END   $name try $n rc=$rc ($(( (SECONDS - start) / 60 ))m $(( (SECONDS - start) % 60 ))s)"
    checkpoint "$name"
    if [[ $rc -eq 0 && -s "$DOCS_DIR/$want" ]]; then return 0; fi
    log "RETRY $name: rc=$rc, $want $([[ -s "$DOCS_DIR/$want" ]] && echo present || echo missing)"
    [[ $n -lt ${#plan[@]} ]] && sleep $(( RETRY_PAUSE * n ))
  done
  log "FAILED $name after $n tries"
  return 1
}

# ---------------- PROMPTS ----------------
read -r -d '' CTX <<'EOF'
Context: you are one of two AI agents (Claude Code and Codex) helping a 3-5 person student team at a one-day hackathon. Agents PREPARE; humans DECIDE. Read CLAUDE.md and README.md first: this repo is the hackkit template, so the infrastructure already exists (LLM providers, extraction with validation, cache, demo mode, HttpConnector, FastAPI + plain HTML/CSS/JS web UI kit with maps and charts, static offline mode, narrate (AI explains, code checks every number), ask (plain-English question -> filter -> deterministic query), provenance badges, golden tests, evals, feature scaffold, and pitch tools: screenshots, slide deck, captioned demo video, Devpost template). Judges score what they SEE in a 3-5 minute pitch: the problem, the impact, the visible AI and a demo with no mistakes. Work only inside this repository. Do not run git. Do not write code: this task produces planning documents in docs/agent/ only. Be concise.
EOF

read -r -d '' P1 <<'EOF'
Task 1 (brief). Read docs/agent/transcript_snapshot.txt. It is a noisy automatic transcript or rough notes of the event kickoff: expect misheard words, cross-talk, and gaps.
Write docs/agent/BRIEF.md with:
1. For EACH challenge mentioned: partner, problem statement as understood, target users, data or APIs provided, constraints and rules, judging criteria, deliverables.
2. Event logistics: times, deadlines, submission method, team assignment information. Quote the transcript line for each fact.
3. Our team assignment: if the transcript says which challenge Le Tuan Nguyen's team got, state it with the exact quote. Otherwise write exactly "ASSIGNMENT: UNKNOWN".
4. "Uncertain or missing": what the team must ask organizers or partners.
Rules: use only the transcript. Mark every inference with [INFERRED]. Never invent numbers, names, or rules.
EOF

read -r -d '' P2 <<'EOF'
Task 2 (critique). Read docs/agent/transcript_snapshot.txt and docs/agent/BRIEF.md. Do NOT edit BRIEF.md.
Write docs/agent/CRITIQUE.md listing: (a) claims in BRIEF.md not supported by the transcript, (b) important transcript details BRIEF.md missed, (c) words that were probably misheard (company names, numbers, times) and what they likely are, (d) risks for the team. Cite transcript lines.
EOF

read -r -d '' P3 <<'EOF'
Task 3 (revise and plan). Read docs/agent/CRITIQUE.md and update docs/agent/BRIEF.md to fix valid points; add a short "Revision notes" section at the end. If CRITIQUE.md says the critique is UNAVAILABLE, instead re-check BRIEF.md against docs/agent/transcript_snapshot.txt yourself and say so in the revision notes.
Then write docs/agent/PLANS.md with one plan per challenge, for a team with about 5 hours of build time. Express each plan in hackkit terms:
- problem in one sentence; the one user; demo flow (input -> processing -> output);
- feature key for `python -m hackkit.scaffold <key>`;
- the Pydantic schema sketch (fields with descriptions; inherit Reviewable);
- what the LLM extracts vs. what deterministic rules() computes (the LLM never does math or rules);
- sponsor or public API calls through HttpConnector, if any;
- the one novel feature that other teams are unlikely to build;
- sample_text / sample_response idea and 3 eval cases (public or synthetic data only);
- at most 6 ordered tasks; top 3 risks; 3 questions to ask the partner before building.
- WINNING (required for every plan):
  * rubric map: each judging criterion (with its weight if stated) -> the feature or demo moment that scores it;
  * the judge's first 10 seconds: what is on screen and the one sentence said;
  * one impact number to show, and where it will come from (partner, public source, or our own measurement; never invented);
  * where the AI is VISIBLE in the main demo flow (extract / narrate / ask), while code still owns every number;
  * prize tracks / sponsor technologies the plan qualifies for, and what using each one would take.
If the assignment is known, put that plan first and mark it ASSIGNED.
EOF

read -r -d '' P4 <<'EOF'
Task 4 (plan review). Read docs/agent/BRIEF.md, docs/agent/PLANS.md, CLAUDE.md and README.md. Do NOT edit them.
Write docs/agent/PLAN_REVIEW.md: for each plan, what is over-scoped for 5 hours, what duplicates something hackkit already provides, what is missing, and a recommended cut-down version (max 4 tasks), and whether the plan's demo would score on EVERY judging criterion (say which criterion is weakest and the cheapest fix). End with a 5-line checklist for the humans to read first.
EOF

# ---------------- SOURCE / CHOICE NOTES ----------------
if [[ ${#WITH_FILES[@]} -gt 0 || $DOC_MODE -eq 1 ]]; then
  P1="SOURCE NOTE (overrides any wording about a noisy transcript below): the snapshot contains one or more SOURCES, each starting with a line that begins with '====='. A DOCUMENT source is an official written statement converted from paper by an AI tool: it has no misheard speech, but it may contain conversion errors, missing tables or garbled numbers, so quote its heading or page marker for each fact and flag numbers that look wrong. A LIVE TRANSCRIPT source is automatic speech-to-text: expect misheard words, cross-talk and gaps. For every fact say which source it comes from. If sources disagree, say so; prefer the written document for requirements and the live transcript for later announcements.

$P1"
  P2="SOURCE NOTE: the snapshot may contain written DOCUMENT sources (look for paper-to-text conversion errors instead of misheard words) and a LIVE TRANSCRIPT source (misheard words). Sources start with a line beginning with '====='.

$P2"
fi
if [[ -n "$CHOSEN" ]]; then
  P1="$P1
OVERRIDE for item 3: the human has ALREADY CHOSEN the team's challenge: \"$CHOSEN\". Do NOT write \"ASSIGNMENT: UNKNOWN\". Write exactly: ASSIGNMENT: $CHOSEN (chosen by the human; the sources do not state an assignment)."
  P3="$P3
The human has ALREADY CHOSEN the team's challenge: \"$CHOSEN\". Write the full plan ONLY for that challenge, mark it ASSIGNED and put it first; give each other challenge at most three sentences."
  P4="$P4
The human has ALREADY CHOSEN the challenge \"$CHOSEN\". Review only that plan in detail; skip the others."
fi

# ---------------- RUN ----------------
log "Planning chain"
if run_step 1_brief claude 15 30 BRIEF.md "$CTX

$P1"; then
  if ! run_step 2_critique codex 10 30 CRITIQUE.md "$CTX

$P2"; then
    printf '# Critique\n\nUNAVAILABLE: the critique step failed on every agent. Treat BRIEF.md as unreviewed.\n' \
      >"$DOCS_DIR/CRITIQUE.md"
  fi
  if run_step 3_plans claude 15 30 PLANS.md "$CTX

$P3"; then
    run_step 4_plan_review codex 10 30 PLAN_REVIEW.md "$CTX

$P4"
  fi
fi

# ---------------- SECRET SCAN ----------------
scan_out="$(python3 "$SCRIPT_DIR/secret_scan.py" --repo "$WT_DIR" --since "$START_SHA" --env "$REPO_DIR/.env" 2>&1)" && scan_rc=0 || scan_rc=$?
SECRET_ALERT=0; [[ $scan_rc -ne 0 ]] && SECRET_ALERT=1

# ---------------- SUMMARY ----------------
{
  echo; echo "## Secret scan"
  if [[ $SECRET_ALERT -eq 1 ]]; then
    echo "**ALERT: a key or secret value was found in the agent output. Do NOT merge agent/plan. Delete the branch.**"
  fi
  echo '```'; echo "$scan_out"; echo '```'
  echo; echo "## Files produced ($(date +%H:%M))"
  for f in BRIEF.md CRITIQUE.md PLANS.md PLAN_REVIEW.md; do
    [[ -s "$DOCS_DIR/$f" ]] && echo "- [x] docs/agent/$f" || echo "- [ ] docs/agent/$f (missing)"
  done
  grep -q '^UNAVAILABLE' <(sed -n '3p' "$DOCS_DIR/CRITIQUE.md" 2>/dev/null) &&
    echo "- NOTE: CRITIQUE.md is only a placeholder (the critique step failed)."
  echo; echo "## Files changed outside docs/agent (should be none)"; echo '```'
  changed="$(git -C "$WT_DIR" diff --name-only "$START_SHA" HEAD | grep -v '^docs/agent/')"
  echo "${changed:-none}"
  echo '```'
  echo; echo "Read first: docs/agent/PLAN_REVIEW.md (checklist at the end), then BRIEF.md."
} >>"$STATUS"
checkpoint "status"
[[ $SECRET_ALERT -eq 1 ]] && log "ALERT: secret found in the agent output, see the Secret scan block. Do NOT merge agent/plan."
log "DONE. See $STATUS"
