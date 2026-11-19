import json
from pathlib import Path

import requests

from ftworthtv.models import ImageAsset, PostCopy, PostDraft, Story
from ftworthtv.publishers.facebook import FacebookPublisher
from ftworthtv.publishers.metricool import MetricoolPublisher


class FakeResponse:
    def __init__(self, payload, status=200):
        self._payload, self.status_code, self.ok, self.content, self.text = payload, status, status < 400, b"x", json.dumps(payload)

    def json(self):
        return self._payload


def _draft(tmp_path, settings):
    story = Story(id="s1", source="Fort Worth Report", source_kind="rss", title="Barbecue opens", summary="S", url="https://example.com/a")
    copy = PostCopy(headline="Barbecue opens", caption="New BBQ 🌮\n\n📍 Fort Worth, TX", first_comment="Source: Fort Worth Report https://example.com/a\n{photo_credit}",
                    hashtags=["#FortWorth", "#FTW"], category="food")
    img = settings.out_dir / "runs" / "r1" / "01-bbq" / "card.jpg"
    img.parent.mkdir(parents=True)
    img.write_bytes(b"\xff\xd8\xff\xd9")
    return PostDraft(story=story, copy=copy, writer="template", mode="photo", image=ImageAsset(path=img, credit="Photo: A via Pexels", license="pexels", provider="pexels"))


def test_facebook_photo_post_and_first_comment(monkeypatch, tmp_path, settings):
    settings.fb_page_id, settings.fb_page_token = "123", "tok"
    calls = []

    def fake_post(url, data=None, files=None, timeout=None):
        calls.append((url, data, files))
        if url.endswith("/123/photos"):
            return FakeResponse({"id": "999", "post_id": "123_555"})
        return FakeResponse({"id": "123_555_777"})

    monkeypatch.setattr(requests, "post", fake_post)
    result = FacebookPublisher(settings).publish(_draft(tmp_path, settings))
    assert result.ok and result.post_id == "123_555" and result.url == "https://www.facebook.com/123_555"
    assert calls[0][0].endswith("/v25.0/123/photos") and "source" in calls[0][2] and calls[0][1]["message"].startswith("New BBQ")
    assert calls[1][0].endswith("/123_555/comments") and "Photo: A via Pexels" in calls[1][1]["message"] and "#FortWorth" in calls[1][1]["message"]


def test_facebook_error_is_reported_not_raised(monkeypatch, tmp_path, settings):
    settings.fb_page_id, settings.fb_page_token = "123", "tok"
    monkeypatch.setattr(requests, "post", lambda *a, **k: FakeResponse({"error": {"message": "Invalid OAuth access token", "type": "OAuthException", "code": 190}}, 400))
    result = FacebookPublisher(settings).publish(_draft(tmp_path, settings))
    assert not result.ok and "OAuthException 190" in result.detail


def test_metricool_builds_public_media_url(monkeypatch, tmp_path, settings):
    settings.metricool_user_token, settings.metricool_user_id, settings.metricool_blog_id = "t", "1", "2"
    settings.root = tmp_path  # out/ lives under tmp in tests; media URLs are built relative to the repo root
    settings.media_base_url = "https://raw.githubusercontent.com/me/repo/main"
    settings.metricool_networks = ["facebook", "instagram"]
    captured = {}

    def fake_post(url, params=None, headers=None, json=None, timeout=None):
        captured.update(url=url, params=params, headers=headers, body=json)
        return FakeResponse({"data": {"id": 42, "plannerUrl": "https://app.metricool.com/planner/42"}})

    monkeypatch.setattr(requests, "post", fake_post)
    monkeypatch.setattr(requests, "head", lambda url, **kw: FakeResponse({}, status=200))   # the image is "public"
    pub = MetricoolPublisher(settings)
    draft = _draft(tmp_path, settings)
    result = pub.publish(draft)
    rel = draft.image.path.relative_to(settings.root).as_posix()
    assert result.ok and result.post_id == "42"
    assert captured["headers"]["X-Mc-Auth"] == "t" and captured["params"] == {"blogId": "2", "userId": "1"}
    assert captured["body"]["media"] == [f"https://raw.githubusercontent.com/me/repo/main/{rel}"]
    assert captured["body"]["providers"] == [{"network": "facebook"}, {"network": "instagram"}]
    assert captured["body"]["facebookData"] == {"type": "POST"} and captured["body"]["publicationDate"]["timezone"] == "America/Chicago"


def test_story_image_and_metricool_story(monkeypatch, tmp_path, settings):
    from ftworthtv.images.card import render_story
    from PIL import Image
    card = tmp_path / "post.jpg"
    Image.new("RGB", (1200, 1000), (200, 200, 200)).save(card)
    out = render_story(card, tmp_path / "story.jpg", brand=settings.brand, fonts_dir=settings.fonts_dir, logo=settings.root / "assets/logo.png")
    with Image.open(out) as im:
        assert im.size == (1080, 1920)
    settings.metricool_user_token, settings.metricool_user_id, settings.metricool_blog_id = "t", "1", "2"
    settings.root = tmp_path
    settings.media_base_url = "https://raw.githubusercontent.com/me/repo/main"
    settings.metricool_networks = ["facebook", "instagram"]
    calls = []

    def fake_post(url, params=None, headers=None, json=None, timeout=None):
        calls.append(json)
        return FakeResponse({"data": {"id": 40 + len(calls), "plannerUrl": "https://app.metricool.com/planner/x"}})

    monkeypatch.setattr(requests, "post", fake_post)
    monkeypatch.setattr(requests, "head", lambda url, **kw: FakeResponse({}, status=200))
    pub = MetricoolPublisher(settings)
    draft = _draft(tmp_path, settings)
    draft.story_path = out
    result = pub.publish(draft)
    assert result.ok and len(calls) == 2
    story = calls[1]
    assert story["facebookData"] == {"type": "STORY"} and story["instagramData"] == {"type": "STORY"} and story["text"] == ""
    assert story["media"][0].endswith("/story.jpg") and "story 42" in result.detail


def test_metricool_video_post_uses_the_hosted_clip(monkeypatch, tmp_path, settings):
    settings.metricool_user_token, settings.metricool_user_id, settings.metricool_blog_id = "t", "1", "2"
    settings.root = tmp_path
    settings.media_base_url = "https://raw.githubusercontent.com/me/repo/main"
    settings.metricool_networks = ["facebook", "instagram"]
    calls = []

    def fake_post(url, params=None, headers=None, json=None, timeout=None):
        calls.append(json)
        return FakeResponse({"data": {"id": 7, "plannerUrl": "https://app.metricool.com/planner/7"}})

    monkeypatch.setattr(requests, "post", fake_post)
    monkeypatch.setattr(requests, "head", lambda url, **kw: FakeResponse({}, status=200))
    draft = _draft(tmp_path, settings)
    draft.mode, draft.image = "video", None
    draft.video_path = tmp_path / "clip.mp4"
    draft.video_path.write_bytes(b"\x00" * 100)
    draft.video_url = "https://github.com/me/repo/releases/download/media-2026-11/r1-01-clip.mp4"
    result = MetricoolPublisher(settings).publish(draft)
    body = calls[-1]
    assert result.ok and body["media"] == [draft.video_url] and body["facebookData"] == {"type": "POST"}
    assert body["providers"] == [{"network": "facebook"}] and "instagramData" not in body     # video.instagram is off by default
    assert "https://example.com/a" not in body["text"]                                         # a video post carries no link
    # with Reels on and a portrait clip, Instagram gets a REEL
    settings.brand["video"] = {"instagram": True}
    import ftworthtv.images.video as video
    monkeypatch.setattr(video, "video_dimensions", lambda path: (720, 1280))
    MetricoolPublisher(settings).publish(draft)
    assert calls[-1]["instagramData"] == {"type": "REEL"} and calls[-1]["providers"] == [{"network": "facebook"}, {"network": "instagram"}]
    monkeypatch.setattr(video, "video_dimensions", lambda path: (1920, 1080))                 # landscape: Facebook only
    MetricoolPublisher(settings).publish(draft)
    assert calls[-1]["providers"] == [{"network": "facebook"}]


def test_queue_reads_the_clip_url_left_by_the_cycle_script(tmp_path, settings):
    import json as _json
    from ftworthtv.queue import load_draft
    folder = tmp_path / "01-clip"
    folder.mkdir()
    (folder / "clip.mp4").write_bytes(b"\x00" * 10)
    (folder / "video_url.txt").write_text("https://github.com/me/repo/releases/download/media-2026-11/x.mp4\n")
    story = {"id": "submission:abc", "source": "Viewer video", "source_kind": "submission", "title": "Hail in Keller", "summary": "Hail in Keller tonight.",
             "url": "", "published": "2026-11-19T20:00:00+00:00", "extra": {"credit": "Jane"}}
    copy = {"headline": "Hail in Keller", "caption": "Hail in Keller tonight.\n\n📍 Keller\n🎥 Video: Jane", "first_comment": "🎥 Jane\n{photo_credit}", "category": "weather"}
    (folder / "post.json").write_text(_json.dumps({"mode": "video", "writer": "template", "video": "clip.mp4", "copy": copy, "story": story}))
    draft = load_draft(folder)
    assert draft.mode == "video" and draft.video_path == folder / "clip.mp4" and draft.video_url.endswith("/x.mp4")
    from ftworthtv.checks import preflight
    assert preflight(draft, network=False) == []
    draft.video_url, draft.video_path = None, folder / "missing.mp4"
    assert "video post without a clip" in preflight(draft, network=False)


def test_metricool_refused_video_falls_back_to_the_card(monkeypatch, tmp_path, settings):
    settings.metricool_user_token, settings.metricool_user_id, settings.metricool_blog_id = "t", "1", "2"
    settings.root = tmp_path
    settings.media_base_url = "https://raw.githubusercontent.com/me/repo/main"
    settings.metricool_networks = ["facebook", "instagram"]
    calls = []

    def fake_post(url, params=None, headers=None, json=None, timeout=None):
        calls.append(json)
        if json["media"] and json["media"][0].endswith(".mp4"):
            return FakeResponse({"error": "video rejected"}, status=400)
        return FakeResponse({"data": {"id": 9, "plannerUrl": "https://app.metricool.com/planner/9"}})

    monkeypatch.setattr(requests, "post", fake_post)
    monkeypatch.setattr(requests, "head", lambda url, **kw: FakeResponse({}, status=200))
    draft = _draft(tmp_path, settings)                       # a radar-loop alert: the card exists, the clip is extra
    draft.mode = "video"
    draft.video_path = tmp_path / "radar.mp4"
    draft.video_path.write_bytes(b"\x00" * 100)
    draft.video_url = "https://github.com/me/repo/releases/download/media-2026-11/r1-01-radar.mp4"
    result = MetricoolPublisher(settings).publish(draft)
    assert result.ok and result.post_id == "9" and len(calls) == 2
    assert calls[0]["media"][0].endswith("radar.mp4") and calls[1]["media"][0].endswith("card.jpg")
    assert calls[1]["providers"] == [{"network": "facebook"}, {"network": "instagram"}]   # the photo post keeps Instagram
