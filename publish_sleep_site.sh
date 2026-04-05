#!/bin/zsh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

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

echo "Done. Cloudflare Pages will deploy automatically after the GitHub push."
