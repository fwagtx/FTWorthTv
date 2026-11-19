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
