#!/usr/bin/env bash
# Host the clips of a run (viewer submissions, the radar loop) on a monthly GitHub release so the scheduler can fetch them,
# and leave each clip's public URL next to it in video_url.txt. Needs GH_TOKEN (contents: write) and GH_REPO (owner/repo).
# Usage: scripts/host_clips.sh [run_dir]   (default: every run under out/runs)
set -uo pipefail
cd "$(dirname "$0")/.."
if [ -z "${GH_REPO:-}" ] || ! command -v gh >/dev/null 2>&1; then
  echo "host_clips: GH_REPO or gh missing; clips stay local"; exit 0
fi
shopt -s nullglob
tag="media-$(date -u +%Y-%m)"
if [ $# -ge 1 ]; then clips=("$1"/*/*.mp4); else clips=(out/runs/*/*/*.mp4); fi
for clip in "${clips[@]}"; do
  dir=$(dirname "$clip")
  [ -e "$dir/video_url.txt" ] && continue
  name="$(basename "$(dirname "$dir")")-$(basename "$dir" | cut -c1-2)-$(basename "$clip")"
  tmp=$(mktemp -d); cp "$clip" "$tmp/$name"
  gh release view "$tag" >/dev/null 2>&1 || gh release create "$tag" --latest=false --title "Post media $tag" \
    --notes "Video files for the page's posts (public hosting for the scheduler)." >/dev/null 2>&1 || true
  if gh release upload "$tag" "$tmp/$name" --clobber >/dev/null 2>&1; then
    url="https://github.com/$GH_REPO/releases/download/$tag/$name"
    echo "$url" > "$dir/video_url.txt"
    echo "clip hosted at $url"
  else
    echo "clip upload failed for $clip (the post will be held)"
  fi
  rm -rf "$tmp"
done
