"""Facebook Pages publishing through the Graph API: photo / link / video posts, first comment, scheduling, token helpers."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import requests

from ..models import PostDraft, PublishResult
from .base import Publisher

log = logging.getLogger(__name__)
GRAPH = "https://graph.facebook.com"


class FacebookError(RuntimeError):
    pass


def _check(resp: requests.Response) -> dict:
    try:
        payload = resp.json()
    except ValueError:
        payload = {"raw": resp.text[:300]}
    if not resp.ok or "error" in payload:
        err = payload.get("error", {})
        raise FacebookError(f"{err.get('type', 'HTTP')} {err.get('code', resp.status_code)}: {err.get('message', payload)}")
    return payload


class FacebookPublisher(Publisher):
    name = "facebook"

    def __init__(self, settings):
        super().__init__(settings)
        if not settings.fb_page_id or not settings.fb_page_token:
            raise FacebookError("FB_PAGE_ID and FB_PAGE_ACCESS_TOKEN are required for the facebook publisher")
        self.base = f"{GRAPH}/{settings.fb_graph_version}"

    def _post(self, path: str, data: dict | None = None, files: dict | None = None) -> dict:
        data = dict(data or {})
        data["access_token"] = self.settings.fb_page_token
        resp = requests.post(f"{self.base}/{path}", data=data, files=files, timeout=180)
        return _check(resp)

    def publish(self, draft: PostDraft) -> PublishResult:
        s = self.settings
        now = datetime.now(timezone.utc)
        caption = draft.caption_text()
        scheduled = draft.scheduled_at and draft.scheduled_at > now + timedelta(minutes=10)
        if scheduled:
            # comments cannot be added to a not-yet-published post, so fold the source credit into the caption
            caption = caption + "\n\n" + draft.first_comment_text()
        data = {"message": caption}
        if scheduled:
            data["published"] = "false"
            data["scheduled_publish_time"] = str(int(draft.scheduled_at.timestamp()))
        if s.fb_place_id:
            data["place"] = s.fb_place_id
        try:
            if draft.mode == "video" and draft.video_path:
                with open(draft.video_path, "rb") as fh:
                    payload = self._post(f"{s.fb_page_id}/videos",
                                         {"description": caption, "title": draft.copy.headline, **({"published": "false", "scheduled_publish_time": data["scheduled_publish_time"]} if scheduled else {})},
                                         files={"source": (draft.video_path.name, fh, "video/mp4")})
                post_id = payload.get("id")
            elif draft.mode == "photo" and draft.image:
                with open(draft.image.path, "rb") as fh:
                    payload = self._post(f"{s.fb_page_id}/photos", data, files={"source": (draft.image.path.name, fh, "image/jpeg")})
                post_id = payload.get("post_id") or payload.get("id")
            elif draft.mode in ("link", "share") and draft.link:
                data["link"] = draft.link   # a public facebook.com post URL renders as a nested shared post
                payload = self._post(f"{s.fb_page_id}/feed", data)
                post_id = payload.get("id")
            else:
                payload = self._post(f"{s.fb_page_id}/feed", data)
                post_id = payload.get("id")
        except (FacebookError, requests.RequestException, OSError) as exc:
            return PublishResult(ok=False, publisher=self.name, detail=str(exc))

        detail = "scheduled" if scheduled else "published"
        comment = draft.first_comment_text()
        if comment and post_id and not scheduled:
            try:
                self._post(f"{post_id}/comments", {"message": comment})
                detail += " + first comment"
            except (FacebookError, requests.RequestException) as exc:
                detail += f" (first comment failed: {exc})"
        if s.ig_user_id and draft.mode == "photo" and draft.image and not scheduled:
            detail += " · " + self.cross_post_instagram(draft, caption)
        url = f"https://www.facebook.com/{post_id}" if post_id else None
        return PublishResult(ok=True, publisher=self.name, post_id=post_id, url=url, detail=detail)

    def cross_post_instagram(self, draft: PostDraft, caption: str) -> str:
        """Free Instagram publishing through the Graph API: needs IG_USER_ID (Business account linked to the Page),
        the same Page token with instagram_basic + instagram_content_publish, and the image on a public URL."""
        from .base import public_media_url
        image_url = public_media_url(draft, self.settings)
        if not image_url:
            return "instagram skipped (set MEDIA_BASE_URL so the image has a public URL)"
        w, h = draft.image.width or 0, draft.image.height or 0
        if w and h and not (0.8 <= w / h <= 1.91):
            return f"instagram skipped (aspect {w}x{h} outside 4:5..1.91:1)"
        try:
            container = self._post(f"{self.settings.ig_user_id}/media", {"image_url": image_url, "caption": caption})
            published = self._post(f"{self.settings.ig_user_id}/media_publish", {"creation_id": container.get("id")})
            return f"instagram published ({published.get('id')})"
        except (FacebookError, requests.RequestException) as exc:
            return f"instagram failed: {exc}"


# ---- token helpers for `ftworthtv fb-token` --------------------------------------------------------
def exchange_long_lived_user_token(app_id: str, app_secret: str, short_token: str, version: str = "v25.0") -> str:
    resp = requests.get(f"{GRAPH}/{version}/oauth/access_token", params={
        "grant_type": "fb_exchange_token", "client_id": app_id, "client_secret": app_secret, "fb_exchange_token": short_token,
    }, timeout=60)
    return _check(resp)["access_token"]


def list_page_tokens(user_token: str, version: str = "v25.0") -> list[dict]:
    """Page tokens obtained from a long-lived user token do not expire (as long as the user keeps the page role)."""
    resp = requests.get(f"{GRAPH}/{version}/me/accounts", params={"access_token": user_token, "fields": "id,name,access_token,tasks"}, timeout=60)
    return _check(resp).get("data", [])


def debug_token(token: str, app_token: str, version: str = "v25.0") -> dict:
    resp = requests.get(f"{GRAPH}/{version}/debug_token", params={"input_token": token, "access_token": app_token}, timeout=60)
    return _check(resp).get("data", {})
