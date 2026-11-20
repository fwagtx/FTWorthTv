"""Command line: run | preview | sources check | fb-token | state | config"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

from dateutil import parser as dtparse

from . import __version__
from .config import Settings


def _settings(args) -> Settings:
    overrides = {}
    if getattr(args, "publisher", None):
        overrides["publisher"] = args.publisher
    if getattr(args, "max", None) is not None:
        overrides["max_posts"] = args.max
    if getattr(args, "since_hours", None) is not None:
        overrides["since_hours"] = args.since_hours
    if getattr(args, "dry_run", False):
        overrides["dry_run"] = True
    if getattr(args, "offline", False):
        overrides["offline"] = True
    return Settings.load(**overrides)


def _stories_from_json(path: Path, now: datetime):
    """A JSON list of story dicts (title, summary, url, source, published?, category_hint?, image_url?...) -> Story objects."""
    from .models import Story
    from .textutil import stable_id
    items = json.loads(path.read_text(encoding="utf-8"))
    stories = []
    for item in items:
        item = dict(item)
        item.setdefault("id", stable_id("json", item.get("url") or item.get("title", "")))
        item.setdefault("source_kind", "rss")
        item.setdefault("summary", "")
        pub = item.get("published")
        item["published"] = dtparse.isoparse(pub) if pub else now
        stories.append(Story(**{k: v for k, v in item.items() if k in Story.__dataclass_fields__}))
    return stories


def cmd_run(args) -> int:
    from .pipeline import run
    settings = _settings(args)
    now = dtparse.isoparse(args.now).astimezone(timezone.utc) if args.now else None
    stories = None
    if getattr(args, "stories", None):
        stories = _stories_from_json(Path(args.stories), now or datetime.now(timezone.utc))
        if not args.no_sources:
            from .sources import collect
            stories += collect(settings, now or datetime.now(timezone.utc))
    only = [k.strip() for k in (args.only_kinds or "").split(",") if k.strip()] or None
    report = run(settings, now=now, stories=stories, publisher_name=args.publisher, only_kinds=only)
    print(report.summary())
    print(f"preview: {report.run_dir / 'preview.html'}")
    return 0 if all(r.ok for r in report.results) else 1


def cmd_preview(args) -> int:
    """Demo run on bundled example data: no network, no keys, no posting. Shows exactly what a run produces."""
    from .examples import example_stories
    from .pipeline import run
    settings = _settings(args)
    settings.offline = True
    settings.publisher = "dryrun"
    settings.max_posts = args.max or 4
    settings.brand.setdefault("card", {})["placeholder_when_no_photo"] = True  # demo data has no photos to fetch
    now = dtparse.isoparse(args.now).astimezone(timezone.utc) if args.now else datetime.now(timezone.utc)
    report = run(settings, now=now, stories=example_stories(settings, now), publisher_name="dryrun")
    print(report.summary())
    print(f"open: {report.run_dir / 'preview.html'}")
    return 0


def cmd_publish(args) -> int:
    """Phase 2 of two-phase publishing: post the drafts of an earlier dry run."""
    from .queue import publish_run
    settings = _settings(args)
    run_dir = Path(args.run_dir)
    if args.run_dir == "latest":
        runs = sorted((settings.out_dir / "runs").glob("*"))
        if not runs:
            print("no runs found", file=sys.stderr)
            return 2
        run_dir = runs[-1]
    if not run_dir.is_absolute():
        run_dir = settings.root / run_dir
    if not run_dir.exists():
        print(f"run dir not found: {run_dir}", file=sys.stderr)
        return 2
    results = publish_run(run_dir, settings, args.publisher or settings.publisher)
    for draft, result in results:
        print(f"{'OK ' if result.ok else 'ERR'} {draft.story.title[:70]} -> {result.publisher}: {result.detail}")
    return 0 if results and all(r.ok for _, r in results) else (0 if not results else 1)


def cmd_sources(args) -> int:
    from .sources import rss
    settings = _settings(args)
    rows = rss.check(settings)
    width = max(len(r["name"]) for r in rows) if rows else 10
    bad = 0
    for r in rows:
        if r["ok"]:
            print(f"OK   {r['name']:<{width}}  {r['items']:>3} items  {r['with_image']:>3} with image  newest {r['newest'] or '-'}")
        else:
            bad += 1
            print(f"FAIL {r['name']:<{width}}  {r['url']}\n     {r['error']}")
    print(f"\n{len(rows) - bad}/{len(rows)} feeds OK. Fix or delete failing entries in config/sources.yaml.")
    return 1 if bad else 0


def cmd_fb_token(args) -> int:
    from .publishers import facebook as fb
    settings = _settings(args)
    app_id = args.app_id or settings.fb_app_id
    app_secret = args.app_secret or settings.fb_app_secret
    if not (app_id and app_secret):
        print("FB_APP_ID and FB_APP_SECRET are required (set them in .env or pass --app-id/--app-secret)", file=sys.stderr)
        return 2
    long_lived = fb.exchange_long_lived_user_token(app_id, app_secret, args.user_token, settings.fb_graph_version)
    print("long-lived USER token obtained (about 60 days). Page tokens below do not expire:\n")
    for page in fb.list_page_tokens(long_lived, settings.fb_graph_version):
        print(f"Page: {page.get('name')}  (id {page.get('id')})\n  FB_PAGE_ID={page.get('id')}\n  FB_PAGE_ACCESS_TOKEN={page.get('access_token')}\n")
    return 0


def cmd_state(args) -> int:
    from .state import State
    settings = _settings(args)
    state = State(settings.state_path)
    if args.action == "prune":
        n = state.prune()
        state.save()
        print(f"pruned {n} old entries")
        return 0
    posted = state.data.get("posted", {})
    print(f"{len(posted)} remembered posts, {state.total_posts} total, last post {state.data.get('last_post_at')}")
    for sid, meta in sorted(posted.items(), key=lambda kv: kv[1]["at"], reverse=True)[: args.limit]:
        print(f"  {meta['at'][:16]}  [{meta.get('category')}] {meta['title'][:70]}  ({meta.get('publisher')} {meta.get('post_id') or ''})")
    return 0


def cmd_session(args) -> int:
    """`session queue RUN --branch B`: write RUN/manifest.json for a reviewing session; `session record RUN --posted JSON`."""
    import json as _json
    from .session import build_manifest, record_posted
    settings = _settings(args)
    run_dir = Path(args.run_dir)
    if not run_dir.is_absolute():
        run_dir = settings.root / run_dir
    if args.action == "queue":
        rows = build_manifest(run_dir, settings, branch=args.branch, repo=args.repo, spacing_minutes=args.spacing)
        out = run_dir / "manifest.json"
        out.write_text(_json.dumps(rows, indent=1, ensure_ascii=False, default=str) + "\n", encoding="utf-8")
        for r in rows:
            if r.get("skip"):
                print(f"SKIP  {r['headline'][:70]}  ({r['skip']})")
                continue
            flag = "HOLD " if r["problems"] else "OK   "
            ph = r.get("photo") or {}
            print(f"{flag} {r['at'][11:16]} [{r['category']}/{r['scope']}] {r['mode']:5} {r['headline'][:70]}")
            print(f"       card: {r['card']}   photo: {ph.get('subject')} | {ph.get('credit')}")
            for pr in r["problems"]:
                print(f"       problem: {pr}")
        print(f"manifest: {out}")
        return 0
    posted = _json.loads(Path(args.posted).read_text(encoding="utf-8")) if Path(args.posted).exists() else _json.loads(args.posted)
    skipped = _json.loads(Path(args.skipped).read_text(encoding="utf-8")) if Path(args.skipped).exists() else _json.loads(args.skipped)
    n = record_posted(run_dir, settings, posted, skipped)
    print(f"recorded {n} post(s) in {settings.state_path}")
    return 0


def cmd_config(args) -> int:
    settings = _settings(args)
    print(json.dumps(settings.redacted(), indent=2, default=str))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="ftworthtv", description="Automated Fort Worth, Texas local news & entertainment page")
    p.add_argument("-v", "--verbose", action="store_true")
    p.add_argument("--version", action="version", version=__version__)
    sub = p.add_subparsers(dest="cmd", required=True)

    def common(sp):
        sp.add_argument("-v", "--verbose", action="store_true", dest="verbose_sub", help=argparse.SUPPRESS)
        sp.add_argument("--publisher", choices=["dryrun", "facebook", "metricool"], help="override FTWTV_PUBLISHER")
        sp.add_argument("--max", type=int, help="max posts this run")
        sp.add_argument("--since-hours", type=int, help="ignore stories older than this")
        sp.add_argument("--dry-run", action="store_true", help="force the dryrun publisher")
        sp.add_argument("--offline", action="store_true", help="never touch the network (placeholder images)")
        sp.add_argument("--now", help="pretend it is this ISO time (testing)")

    r = sub.add_parser("run", help="collect, write, illustrate and publish")
    common(r)
    r.add_argument("--stories", help="JSON file of extra stories to consider (real headlines, submissions)")
    r.add_argument("--no-sources", action="store_true", help="with --stories: use only the JSON stories, skip the feeds")
    r.add_argument("--only-kinds", help="comma list of source kinds to consider, e.g. wanted,arrest_log (preview one source)")
    r.set_defaults(func=cmd_run)
    pv = sub.add_parser("preview", help="demo on bundled example stories, no network/keys needed")
    common(pv)
    pv.set_defaults(func=cmd_preview)
    pb = sub.add_parser("publish", help="publish the drafts of a previous dry run folder (two-phase posting)")
    pb.add_argument("run_dir", help="e.g. out/runs/20261117-181500 (or 'latest')")
    pb.add_argument("--publisher", choices=["dryrun", "facebook", "metricool"])
    pb.set_defaults(func=cmd_publish)
    s = sub.add_parser("sources", help="check that every RSS feed in config/sources.yaml works")
    s.add_argument("action", choices=["check"])
    s.set_defaults(func=cmd_sources)
    t = sub.add_parser("fb-token", help="turn a short-lived Facebook user token into a permanent Page token")
    t.add_argument("--user-token", required=True, help="short-lived user token from Graph API Explorer")
    t.add_argument("--app-id")
    t.add_argument("--app-secret")
    t.set_defaults(func=cmd_fb_token)
    st = sub.add_parser("state", help="show or prune the posted-items memory")
    st.add_argument("action", choices=["show", "prune"], nargs="?", default="show")
    st.add_argument("--limit", type=int, default=20)
    st.set_defaults(func=cmd_state)
    se = sub.add_parser("session", help="publish from a Claude session: queue a rendered run for review, record what was scheduled")
    se.add_argument("action", choices=["queue", "record"])
    se.add_argument("run_dir")
    se.add_argument("--branch", default="", help="renders/<run>-<n> branch the run folder was pushed to")
    se.add_argument("--repo", default="fwagtx/FTWorthTv")
    se.add_argument("--spacing", type=int, default=None, help="minutes between posts (default: brand.yaml)")
    se.add_argument("--posted", default="{}", help="JSON file or string: {story_id: {post_id, story_post_id, at, url}}")
    se.add_argument("--skipped", default="{}", help="JSON file or string: {story_id: reason} for drafts the session did not post")
    se.set_defaults(func=cmd_session)
    c = sub.add_parser("config", help="print the resolved settings (secrets masked)")
    c.set_defaults(func=cmd_config)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    verbose = args.verbose or getattr(args, "verbose_sub", False)
    logging.basicConfig(level=logging.DEBUG if verbose else logging.INFO, format="%(levelname)-7s %(name)s: %(message)s")
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("httpx2").setLevel(logging.WARNING)
    return args.func(args)
