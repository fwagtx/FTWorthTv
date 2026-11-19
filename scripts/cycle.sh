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
if { [ "$PUBLISHER" != "dryrun" ] || [ "${FTWTV_HOST_CLIPS:-}" = "1" ]; } && [ -n "${GH_REPO:-}" ] && command -v gh >/dev/null 2>&1; then
  shopt -s nullglob
  tag="media-$(date -u +%Y-%m)"
  for clip in out/runs/*/*/*.mp4; do
    dir=$(dirname "$clip"); [ -e "$dir/video_url.txt" ] && continue
    name="$(basename "$(dirname "$dir")")-$(basename "$dir" | cut -c1-2)-$(basename "$clip")"
    tmp=$(mktemp -d); cp "$clip" "$tmp/$name"
    gh release view "$tag" >/dev/null 2>&1 || gh release create "$tag" --latest=false --title "Post media $tag" \
      --notes "Video files for the page's posts (public hosting for the scheduler)." >/dev/null 2>&1 || true
    if gh release upload "$tag" "$tmp/$name" --clobber >/dev/null 2>&1; then
      echo "https://github.com/$GH_REPO/releases/download/$tag/$name" > "$dir/video_url.txt"
      echo "clip hosted at $(cat "$dir/video_url.txt")"
    else
      echo "clip upload failed for $clip (the post will be held)"
    fi
    rm -rf "$tmp"
  done
fi

if [ "$PUBLISHER" != "dryrun" ]; then
  python -m ftworthtv publish latest --publisher "$PUBLISHER" || echo "publish step reported a failure"
fi

git add state/posted.json 2>/dev/null || true
git diff --cached --quiet || (git commit -q -m "chore: update post memory [skip ci]" && git pull -q --rebase --autostash && git push -q)
