import json

from ftworthtv.examples import example_stories
from ftworthtv.pipeline import in_quiet_hours, run
from ftworthtv.queue import load_draft, publish_run


def test_offline_dry_run_end_to_end(settings, now):
    settings.max_posts = 3
    report = run(settings, now=now, stories=example_stories(settings, now), publisher_name="dryrun")
    assert report.candidates >= 15
    assert len(report.drafts) == 3 and all(r.ok for r in report.results)
    assert report.drafts[0].story.source_kind == "nws_alert"          # severe weather first
    assert report.drafts[1].scheduled_at is not None                    # later posts are spaced out
    for draft in report.drafts:
        assert draft.image and draft.image.path.exists()
        folder = draft.image.path.parent
        assert (folder / "post.json").exists() and (folder / "caption.txt").exists()
    assert (report.run_dir / "preview.html").exists() and (report.run_dir / "report.json").exists()
    assert (settings.out_dir / "latest-preview.html").exists()
    assert not settings.state_path.exists()                             # dry runs never touch the real memory
    assert (report.run_dir / "state-after-dry-run.json").exists()


def test_two_phase_publish_reloads_drafts(settings, now):
    settings.max_posts = 2
    report = run(settings, now=now, stories=example_stories(settings, now), publisher_name="dryrun")
    folder = report.drafts[0].image.path.parent
    draft = load_draft(folder)
    assert draft and draft.story.title == report.drafts[0].story.title and draft.image.path.exists()
    results = publish_run(report.run_dir, settings, "dryrun")
    assert len(results) == 2 and all(r.ok for _, r in results)


def test_quiet_hours_only_allow_urgent(settings, now):
    from datetime import datetime, timezone
    late = datetime(2026, 11, 20, 8, 30, tzinfo=timezone.utc)  # 2:30am Central
    assert in_quiet_hours(late.astimezone(settings.tz), [23, 6])
    report = run(settings, now=late, stories=example_stories(settings, late), publisher_name="dryrun")
    assert all(d.story.is_urgent for d in report.drafts) and len(report.drafts) == 1


def test_link_mode_for_news(settings, now):
    settings.brand["posting"]["news_photo_mode"] = "link"
    settings.max_posts = 3
    report = run(settings, now=now, stories=[s for s in example_stories(settings, now) if s.source_kind == "rss"], publisher_name="dryrun")
    assert report.drafts and all(d.mode == "link" and d.link for d in report.drafts)
    data = json.loads((report.run_dir / "report.json").read_text())
    assert data["posts"][0]["mode"] == "link"


def test_outlet_story_without_a_verified_photo_is_skipped_not_linked(settings, now):
    from datetime import timedelta
    from ftworthtv.models import Story
    story = Story(id="l1", source="FOX 4 Dallas-Fort Worth", source_kind="rss", title="Fort Worth country club expels Bo French after social media controversies",
                  summary="A Fort Worth country club has expelled Bo French, the Tarrant County Republican chairman, after a series of social media posts.",
                  url="https://www.fox4news.com/news/fort-worth-country-club-bo-french", published=now - timedelta(hours=1), category_hint="politics", extra={"scope": "local"})
    settings.max_posts = 1
    report = run(settings, now=now, stories=[story], publisher_name="dryrun")
    assert not report.drafts and any(why == "no picture of the subject that we may use" for _, why in report.skipped)
    settings.brand["posting"]["link_when_no_photo"] = True                 # the old behaviour stays available, off by default
    report = run(settings, now=now, stories=[story], publisher_name="dryrun")
    assert report.drafts and report.drafts[0].mode == "link"


def test_session_manifest_and_record(settings, now):
    import json as _json
    from ftworthtv.session import build_manifest, record_posted
    settings.max_posts = 2
    report = run(settings, now=now, stories=example_stories(settings, now), publisher_name="dryrun")
    rows = build_manifest(report.run_dir, settings, branch="renders/test-1", repo="me/repo", start=now)
    live = [r for r in rows if not r.get("skip")]
    assert len(live) == 2 and live[0]["image_url"].startswith("https://raw.githubusercontent.com/me/repo/renders/test-1/out/runs/")
    assert live[0]["metricool"]["post"]["media"] == [live[0]["image_url"]] and live[0]["metricool"]["post"]["facebookData"] == {"type": "POST"}
    assert live[0]["metricool"]["story"]["facebookData"] == {"type": "STORY"} and live[1]["at"] > live[0]["at"]
    n = record_posted(report.run_dir, settings, {live[0]["story_id"]: {"post_id": "123", "story_post_id": "124", "at": now.isoformat()}})
    assert n == 1
    from ftworthtv.state import State
    assert State(settings.state_path).has(live[0]["story_id"])
    rows2 = build_manifest(report.run_dir, settings, branch="renders/test-1", repo="me/repo", start=now)
    assert any(r.get("skip") == "already posted" for r in rows2)


def test_session_manifest_uses_the_brand_networks(settings, now):
    from ftworthtv.session import build_manifest
    settings.brand.setdefault("posting", {})["networks"] = ["facebook", "instagram"]
    settings.max_posts = 1
    report = run(settings, now=now, stories=example_stories(settings, now), publisher_name="dryrun")
    live = [r for r in build_manifest(report.run_dir, settings, branch="renders/t", repo="me/repo", start=now) if not r.get("skip")]
    nets = [p["network"] for p in live[0]["metricool"]["post"]["providers"]]
    assert nets == ["facebook", "instagram"] and live[0]["metricool"]["post"]["instagramData"]["type"] == "POST"


def test_posts_scheduled_ahead_do_not_block_the_next_render(settings, now):
    from datetime import timedelta
    from ftworthtv.session import build_manifest, record_posted
    settings.max_posts = 1
    first = run(settings, now=now, stories=example_stories(settings, now), publisher_name="dryrun")
    rows = [r for r in build_manifest(first.run_dir, settings, branch="renders/t", repo="me/repo", start=now) if not r.get("skip")]
    later = now + timedelta(minutes=50)                                   # the session scheduled it for later
    record_posted(first.run_dir, settings, {rows[0]["story_id"]: {"post_id": "1", "at": later.isoformat()}})
    second = run(settings, now=now + timedelta(minutes=5), stories=example_stories(settings, now), publisher_name="dryrun")
    assert second.drafts and not any("too soon" in n for n in second.notes)
    rows2 = [r for r in build_manifest(second.run_dir, settings, branch="renders/t", repo="me/repo", start=now + timedelta(minutes=5)) if not r.get("skip")]
    from datetime import datetime as _dt
    assert _dt.fromisoformat(rows2[0]["at"]) >= later + timedelta(minutes=25)


def test_wanted_bulletins_have_a_daily_cap(settings, now):
    from datetime import timedelta
    from ftworthtv.models import PostDraft, PostCopy, PublishResult, Story
    from ftworthtv.state import State
    settings.sources.setdefault("wanted", {})["max_per_day"] = 1
    settings.state_path.parent.mkdir(parents=True, exist_ok=True)
    state = State(settings.state_path)
    earlier = Story(id="w0", source="Fort Worth Police Department", source_kind="wanted", title="WANTED: Someone Else", summary="", url="https://police.fortworthtexas.gov/x",
                    published=now - timedelta(hours=3), category_hint="crime", extra={"name": "Someone Else", "agency": "Fort Worth Police Department", "charge": "Theft"})
    state.record(PostDraft(story=earlier, copy=PostCopy(category="crime", headline="h", caption="c", first_comment=""), writer="template"), PublishResult(ok=True, publisher="dryrun", post_id="1"),
                 now - timedelta(hours=3), now.astimezone(settings.tz).date().isoformat())
    state.save()
    settings.max_posts = 3
    fresh = Story(id="w1", source="Fort Worth Police Department", source_kind="wanted", title="WANTED: Test Person",
                  summary="Test Person is wanted by the Fort Worth Police Department for Theft in Fort Worth, Tarrant County.", url="https://police.fortworthtexas.gov/y",
                  published=now - timedelta(hours=1), category_hint="crime",
                  extra={"name": "Test Person", "agency": "Fort Worth Police Department", "charge": "Theft", "reward": "$2,000",
                         "tip_phone": "817-469-TIPS (8477)", "tip_url": "https://police.fortworthtexas.gov/y", "city": "Fort Worth", "scope": "local"})
    report = run(settings, now=now, stories=[fresh], publisher_name="dryrun")
    assert not any(d.story.source_kind == "wanted" for d in report.drafts)
    assert any(reason == "wanted bulletins for today are used up" for _, reason in report.skipped)


def test_a_play_that_happened_never_takes_the_stadium_as_a_stand_in(settings, now):
    from datetime import timedelta
    from ftworthtv.models import Story
    story = Story(id="p1", source="NBC 5 DFW (AP)", source_kind="rss", title="Cowboys beat Eagles 24-17 at AT&T Stadium as Dak Prescott throws three touchdowns",
                  summary="The Dallas Cowboys beat the Philadelphia Eagles 24-17 on Thursday at AT&T Stadium in Arlington.", url="https://www.nbcdfw.com/x",
                  published=now - timedelta(hours=2), category_hint="sports", extra={"scope": "local"})
    settings.max_posts = 1
    report = run(settings, now=now, stories=[story], publisher_name="dryrun")
    assert report.drafts and report.drafts[0].image.provider == "card"   # no picture of the play: a text card, never the stadium, never a link preview
    assert any(n.startswith("text card") for n in report.notes)          # and the run says so


def test_a_cap_held_draft_is_remembered_for_tomorrow(settings, now):
    import json as _json
    from datetime import datetime as _dt, timedelta, timezone as _tz
    from ftworthtv.session import cap_held, record_posted
    from ftworthtv.state import State
    run_dir = settings.state_path.parent / "run-held"
    run_dir.mkdir(parents=True)
    (run_dir / "report.json").write_text(_json.dumps({"posts": [], "skipped_by_writer": [
        {"title": "Fort Worth ISD serves free meals during Thanksgiving break", "reason": "daily cap for community reached", "id": "meals", "published": now.isoformat()},
        {"title": "Fort Worth forecast for Tuesday", "reason": "dated for a day that has passed", "id": "fc", "published": None},
        {"title": "an old report without ids", "reason": "daily cap for sports reached"},
    ]}), encoding="utf-8")
    assert cap_held(run_dir) == [("meals", "Fort Worth ISD serves free meals during Thanksgiving break", "daily cap for community reached")]
    assert record_posted(run_dir, settings, {}, {}) == 0                     # nothing posted, nothing skipped by hand
    state = State(settings.state_path)
    assert state.deferred("meals") and not state.deferred("fc")
    state.prune(_dt.now(_tz.utc) + timedelta(hours=49))
    assert not state.deferred("meals")                                        # forgotten two days later


def test_the_writer_looks_past_candidates_the_caps_hold_back(settings, now):
    from datetime import timedelta
    from ftworthtv.models import Story
    settings.max_posts = 1
    settings.brand.setdefault("content_mix", {})["caps_per_day"] = {"community": 0, "business": 0, "weather": 0}

    def story(sid, title, cat, weight=1.5):
        return Story(id=sid, source=f"desk-{sid}", source_kind="rss", title=title, summary="The change starts Monday, the city said in a release.",
                     url=f"https://x/{sid}", published=now - timedelta(hours=1), category_hint=cat, always_relevant=True, weight=weight)
    held = [story("c", "Fort Worth opens a new senior center in Como", "community"),
            story("b", "Fort Worth water rates will rise 4 percent in January", "business"),
            story("w", "Fort Worth cools into the 40s this weekend", "weather")]
    fourth = story("p", "TCU football sets kickoff times for the last two home games", "sports", weight=1.0)
    report = run(settings, now=now, stories=held + [fourth], publisher_name="dryrun")
    assert sum(1 for _, r in report.skipped if r.startswith("daily cap for")) == 3
    seen = {d.story.id for d in report.drafts} | {s.id for s, _ in report.skipped}
    assert "p" in seen                                   # the fourth candidate was written, not starved by the three the caps held


def test_wanted_bulletins_do_not_use_up_the_crime_cap(settings, now):
    from datetime import timedelta
    from ftworthtv.models import PostDraft, PostCopy, PublishResult, Story
    from ftworthtv.state import State
    settings.brand.setdefault("content_mix", {})["caps_per_day"] = {"crime": 2}
    settings.state_path.parent.mkdir(parents=True, exist_ok=True)
    state = State(settings.state_path)
    day = now.astimezone(settings.tz).date().isoformat()
    for i in range(2):                                                   # the morning's two bulletins
        w = Story(id=f"w{i}", source="Fort Worth Police Department", source_kind="wanted", title=f"WANTED: Person {i}", summary="", url=f"https://police.fortworthtexas.gov/{i}",
                  published=now - timedelta(hours=3), category_hint="crime", extra={"name": f"Person {i}", "agency": "Fort Worth Police Department", "charge": "Theft"})
        state.record(PostDraft(story=w, copy=PostCopy(category="crime", headline="h", caption="c", first_comment=""), writer="template"),
                     PublishResult(ok=True, publisher="dryrun", post_id=str(i)), now - timedelta(hours=3), day)
    state.save()
    settings.max_posts = 1
    news = Story(id="n", source="FOX 4 Dallas-Fort Worth", source_kind="rss", title="Arlington pastor convicted in $6M real estate and investment fraud scheme",
                 summary="An Arlington pastor was convicted Thursday of defrauding followers out of more than $6 million, prosecutors said.", url="https://x/n",
                 published=now - timedelta(hours=1), always_relevant=True)
    report = run(settings, now=now, stories=[news], publisher_name="dryrun")
    reasons = [r for s, r in report.skipped if s.id == "n"]
    assert not any(r.startswith("daily cap for crime") for r in reasons)     # the conviction is judged on its own, not silenced by bulletins


def test_a_candidate_that_fails_does_not_spend_the_non_local_share(settings, now, monkeypatch):
    from datetime import timedelta
    from ftworthtv.models import Story
    monkeypatch.setenv("FTWTV_NON_LOCAL_PER_RUN", "1")
    settings.max_posts = 2
    first = Story(id="d1", source="FOX 4 Dallas-Fort Worth", source_kind="rss", title="Police shot at suspected burglars in Far East Dallas, no injuries reported",
                  summary="Dallas police fired at two suspected burglars early Saturday, the department said. Nobody was hurt.", url="https://x/d1",
                  published=now - timedelta(hours=1), always_relevant=True, extra={"scope": "dfw"})
    second = Story(id="d2", source="NBC 5 DFW", source_kind="rss", title="DFW Weather: Dry weather expected Wednesday across Texas before Thanksgiving",
                   summary="Travelers across North Texas can expect dry roads Wednesday, the NBC 5 forecast says.", url="https://x/d2",
                   published=now - timedelta(hours=1), always_relevant=True, extra={"scope": "dfw"})
    report = run(settings, now=now, stories=[first, second], publisher_name="dryrun")
    reasons = {s.id: r for s, r in report.skipped}
    assert "share used" not in reasons.get("d2", "")              # the first story failed on its picture: the share is still there for the second


def test_a_render_for_the_session_does_not_wait_out_the_posting_gap(settings, now):
    from datetime import timedelta
    from ftworthtv.state import State
    settings.state_path.parent.mkdir(parents=True, exist_ok=True)
    state = State(settings.state_path)
    state.data["last_post_at"] = (now - timedelta(minutes=10)).isoformat()      # the session's last post went out ten minutes ago
    state.save()
    settings.max_posts = 2
    report = run(settings, now=now, stories=example_stories(settings, now), publisher_name="dryrun")
    assert report.drafts and not any("too soon" in n for n in report.notes)     # the manifest spaces the next post; the render drafts anyway


def test_hard_news_without_a_picture_goes_out_as_a_text_card_and_soft_news_waits(settings, now):
    from datetime import timedelta
    from ftworthtv.models import Story
    settings.brand.setdefault("card", {})["placeholder_when_no_photo"] = False      # the live setting: no fake skyline
    settings.max_posts = 2
    death = Story(id="c", source="WFAA", source_kind="rss", title="Dallas Cowboys fan dies after altercation during 49ers game, Arlington police say",
                  # the clock is a Thursday: the game was the night before (a death four days gone would be stale_happening)
                  summary="A man died after an altercation in the stands during Wednesday's game at AT&T Stadium, Arlington police said Thursday.", url="https://x/c",
                  published=now - timedelta(hours=1), always_relevant=True, category_hint="crime")
    cafe = Story(id="f", source="CultureMap Fort Worth", source_kind="rss", title="A new coffee shop opens on Magnolia Avenue this weekend",
                 summary="The shop opens Saturday with pastries from a local bakery, the owners said.", url="https://x/f",
                 published=now - timedelta(hours=1), always_relevant=True, category_hint="food")
    report = run(settings, now=now, stories=[death, cafe], publisher_name="dryrun")
    ids = [d.story.id for d in report.drafts]
    assert "c" in ids and report.drafts[ids.index("c")].image.provider == "card"   # an original post with nothing to mismatch
    assert "f" not in ids and any(s.id == "f" and r.startswith("no picture") for s, r in report.skipped)


def test_a_sports_result_without_a_picture_goes_out_as_a_text_card(settings, now):
    from datetime import timedelta
    from ftworthtv.models import Story
    settings.brand.setdefault("card", {})["placeholder_when_no_photo"] = False
    settings.max_posts = 1
    game = Story(id="hs", source="Fort Worth Star-Telegram", source_kind="rss", title="Wilmer-Hutchins and White Settlement Brewer keep playoff hopes alive",
                 summary="Brewer beat Wilmer-Hutchins 28-21 on Wednesday night to stay alive in the playoffs, the coaches said.", url="https://x/hs",
                 published=now - timedelta(hours=1), always_relevant=True, category_hint="sports")
    report = run(settings, now=now, stories=[game], publisher_name="dryrun")
    assert [d.story.id for d in report.drafts] == ["hs"] and report.drafts[0].image.provider == "card"


def test_kinds_whose_daily_share_is_spent_do_not_fill_the_writer_pool(settings, now):
    """Nov 21, 10:49 pm: six wanted bulletins (the day's two already out) and three videos (share used) took the pool's
    slots and the Mavericks' recap, ranked lower, was never written."""
    from datetime import timedelta
    from ftworthtv.models import Story
    settings.max_posts = 1
    settings.sources.setdefault("wanted", {})["max_per_day"] = 0
    settings.sources.setdefault("youtube", {})["max_per_day"] = 0

    def stuck(i, kind):
        return Story(id=f"{kind}{i}", source=f"agency-{i}", source_kind=kind, title=f"WANTED: Person Number{i}" if kind == "wanted" else f"Fort Worth clip {i}",
                     summary="Police are asking for help finding this person, the department said.", url=f"https://x/{kind}{i}",
                     published=now - timedelta(minutes=30), category_hint="crime" if kind == "wanted" else "community", always_relevant=True, weight=3.0)
    blockers = [stuck(i, "wanted") for i in range(10)] + [stuck(i, "video") for i in range(6)]
    recap = Story(id="mavs", source="WFAA Sports", source_kind="rss", title="Mavericks beat the Clippers 110-100 behind Irving and Flagg in Dallas",
                  summary="Kyrie Irving scored 25 points and Cooper Flagg had 22 as the Dallas Mavericks beat the Los Angeles Clippers 110-100 on Wednesday night.",
                  url="https://x/mavs", published=now - timedelta(hours=1), category_hint="sports", always_relevant=True, weight=0.5)
    report = run(settings, now=now, stories=blockers + [recap], publisher_name="dryrun")
    reasons = {s.id: r for s, r in report.skipped}
    assert reasons.get("wanted3") == "wanted bulletins for today are used up" and reasons.get("video2", "").startswith("video share used")
    seen = {d.story.id for d in report.drafts} | {s.id for s, r in report.skipped if not r.startswith(("wanted", "video"))}
    assert "mavs" in seen                                 # written (or judged by the writer), not starved by sixteen stuck candidates


def test_last_post_at_keeps_the_latest_time_whatever_order_posts_are_recorded(settings):
    """Nov 22: the 8:10 wanted bulletin was recorded before the 7:45 TCU post, and last_post_at went back to 7:45."""
    from datetime import datetime, timezone
    from ftworthtv.models import PostCopy, PostDraft, PublishResult, Story
    from ftworthtv.state import State
    state = State(settings.state_path)
    def draft(sid):
        story = Story(id=sid, source="x", source_kind="rss", title=f"story {sid}", summary="", url=f"https://x/{sid}")
        copy = PostCopy(skip=False, skip_reason="", category="community", headline="h", caption="c", first_comment="", hashtags=[], image_query="", location="")
        return PostDraft(story=story, copy=copy, writer="template", image=None, mode="photo")
    late = datetime(2026, 11, 22, 14, 10, tzinfo=timezone.utc)
    early = datetime(2026, 11, 22, 13, 45, tzinfo=timezone.utc)
    state.record(draft("a"), PublishResult(ok=True, publisher="metricool"), late, "2026-11-22")
    state.record(draft("b"), PublishResult(ok=True, publisher="metricool"), early, "2026-11-22")
    assert state.last_post_at == late


def test_categories_whose_daily_cap_is_spent_do_not_fill_the_writer_pool(settings, now):
    """Nov 23, render 167: community, crime and weather stories whose daily caps were used took the pool's slots, and NBC 5's
    "TCU interim HC Andy Avalos introduced ahead of regular-season finale", ranked lower, was never written."""
    from datetime import timedelta
    from ftworthtv.models import Story
    settings.max_posts = 1
    settings.brand.setdefault("content_mix", {}).setdefault("caps_per_day", {})["community"] = 0

    def stuck(i):
        return Story(id=f"comm{i}", source=f"outlet-{i}", source_kind="rss", title=f"Fort Worth library hosts holiday craft day number {i}",
                     summary="The Fort Worth Public Library will host a holiday craft day for families this weekend, the city said.",
                     url=f"https://x/comm{i}", published=now - timedelta(minutes=30), category_hint="community", always_relevant=True, weight=3.0)
    tcu = Story(id="tcu", source="NBC 5 DFW", source_kind="rss", title="TCU interim HC Andy Avalos introduced ahead of regular-season finale against TTU",
                summary="TCU introduced Andy Avalos as interim head coach on Monday ahead of the Horned Frogs' regular-season finale against Texas Tech.",
                url="https://x/tcu", published=now - timedelta(hours=1), category_hint="sports", always_relevant=True, weight=0.5)
    report = run(settings, now=now, stories=[stuck(i) for i in range(16)] + [tcu], publisher_name="dryrun")
    reasons = {s.id: r for s, r in report.skipped}
    assert reasons.get("comm3") == "daily cap for community reached"
    seen = {d.story.id for d in report.drafts} | {s.id for s, r in report.skipped if not r.startswith("daily cap")}
    assert "tcu" in seen                                  # written (or judged by the writer), not starved by sixteen capped stories
