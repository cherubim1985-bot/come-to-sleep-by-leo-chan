#!/bin/zsh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

if [[ $# -eq 0 ]]; then
  echo "Usage: ./publish_sleep_site.sh --theme-name 'Still Waters at Night' --duration-minutes 23 [--date YYYY-MM-DD]"
  exit 1
fi

PIPELINE_ARGS=("$@")
HAS_SINGLE_LATEST=0

for arg in "${PIPELINE_ARGS[@]}"; do
  if [[ "$arg" == "--website-single-latest" ]]; then
    HAS_SINGLE_LATEST=1
    break
  fi
done

if [[ $HAS_SINGLE_LATEST -eq 0 ]]; then
  PIPELINE_ARGS+=("--website-single-latest")
fi

echo "Generating latest session and refreshing Netlify publish directory..."
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
git -C "$ROOT_DIR" push

echo "Done. Netlify will deploy automatically."
