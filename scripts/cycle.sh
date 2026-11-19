#!/usr/bin/env bash
# One posting cycle: generate (always a dry run on disk), publish the committed images if a real publisher is set, then
# remember what was posted. Used once by post.yml and in a loop by watch.yml. Needs the same environment as post.yml.
set -uo pipefail
cd "$(dirname "$0")/.."
PUBLISHER="${FTWTV_PUBLISHER:-dryrun}"
git config user.name "ftworthtv-bot"
git config user.email "ftworthtv-bot@users.noreply.github.com"
git pull -q --rebase --autostash || true

python -m ftworthtv run --publisher dryrun ${FTWTV_ONLY_KINDS:+--only-kinds "$FTWTV_ONLY_KINDS"} ${FTWTV_NOW:+--now "$FTWTV_NOW"} || { echo "generation failed"; exit 0; }

if [ "$PUBLISHER" = "metricool" ] || [ -n "${IG_USER_ID:-}" ]; then
  shopt -s nullglob
  files=(out/runs/*/*/post.jpg out/runs/*/*/card.jpg out/runs/*/*/photo.jpg out/runs/*/*/quote.jpg out/runs/*/*/story.jpg)
  if [ ${#files[@]} -gt 0 ]; then
    git add -f "${files[@]}"
    git diff --cached --quiet || (git commit -q -m "media: post images $(date -u +%Y-%m-%dT%H:%MZ) [skip ci]" && git push -q)
  fi
fi

# Native clips (viewer submissions, the radar loop) need a public URL for the scheduler: a monthly GitHub release holds them.
if [ "$PUBLISHER" != "dryrun" ] || [ "${FTWTV_HOST_CLIPS:-}" = "1" ]; then
  bash scripts/host_clips.sh
fi

if [ "$PUBLISHER" != "dryrun" ]; then
  python -m ftworthtv publish latest --publisher "$PUBLISHER" || echo "publish step reported a failure"
fi

git add state/posted.json 2>/dev/null || true
git diff --cached --quiet || (git commit -q -m "chore: update post memory [skip ci]" && git pull -q --rebase --autostash && git push -q)
