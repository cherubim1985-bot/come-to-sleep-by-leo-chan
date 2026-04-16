#!/bin/zsh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"
LIVE_SITE_URL="${LIVE_SITE_URL:-https://come-to-sleep-by-leo-chan.pages.dev}"

verify_live_site() {
  if ! command -v curl >/dev/null 2>&1; then
    echo "Live site verification skipped: curl is not installed."
    return 0
  fi

  local local_summary
  local live_json
  local live_summary
  local_summary="$(
    python3 - "$ROOT_DIR/website/sessions.json" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
payload = json.loads(path.read_text(encoding="utf-8"))
sessions = payload.get("sessions") or []
latest = sessions[0] if sessions else {}
print("|".join([
    str(payload.get("updated_at", "")),
    str(payload.get("session_count", len(sessions))),
    str(latest.get("slug", "")),
]))
PY
  )"

  live_json="$(curl -fsSL "${LIVE_SITE_URL%/}/sessions.json?codex_verify=$(date +%s)" 2>/dev/null || true)"
  live_summary="$(
    LIVE_JSON="$live_json" python3 - <<'PY' || true
import json
import os
import sys

try:
    payload = json.loads(os.environ.get("LIVE_JSON", ""))
except Exception:
    sys.exit(1)
sessions = payload.get("sessions") or []
latest = sessions[0] if sessions else {}
print("|".join([
    str(payload.get("updated_at", "")),
    str(payload.get("session_count", len(sessions))),
    str(latest.get("slug", "")),
]))
PY
  )"

  if [[ -n "$live_summary" && "$live_summary" == "$local_summary" ]]; then
    echo "Live site verified: ${LIVE_SITE_URL%/}/sessions.json matches the local library."
  else
    echo "WARNING: GitHub was updated, but the live site does not match the local library yet."
    echo "Local summary: $local_summary"
    echo "Live summary:  ${live_summary:-unreachable or invalid JSON}"
    echo "Fix the hosting project so it deploys this repo/branch, or manually upload deploy/cloudflare-pages."
    return 1
  fi
}

if [[ $# -eq 0 ]]; then
  echo "Usage: ./publish_sleep_site.sh --theme-name 'Still Waters at Night' --duration-minutes 23 [--date YYYY-MM-DD] [--website-single-latest]"
  exit 1
fi

PIPELINE_ARGS=("$@")

echo "Generating latest session and refreshing publish directories..."
python3 "$ROOT_DIR/daily_meditation_pipeline.py" "${PIPELINE_ARGS[@]}"

echo "Staging website updates..."
git -C "$ROOT_DIR" add .

if git -C "$ROOT_DIR" diff --cached --quiet; then
  echo "No changes to commit."
  verify_live_site
  exit 0
fi

COMMIT_MESSAGE="Update sleep site $(date '+%Y-%m-%d %H:%M:%S')"
echo "Creating commit: $COMMIT_MESSAGE"
git -C "$ROOT_DIR" commit -m "$COMMIT_MESSAGE"

echo "Pushing to GitHub..."
CURRENT_BRANCH="$(git -C "$ROOT_DIR" branch --show-current)"
if [[ -n "$CURRENT_BRANCH" ]]; then
  git -C "$ROOT_DIR" push origin "$CURRENT_BRANCH"
else
  git -C "$ROOT_DIR" push origin HEAD:main
fi

echo "GitHub push complete. Checking the live site..."
verify_live_site
