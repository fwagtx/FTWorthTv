"""Data model shared by sources, writer, image pipeline and publishers."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel, Field

CATEGORIES = ["breaking", "crime", "traffic", "weather", "events", "food", "sports",
              "culture", "community", "business", "politics", "other"]
Category = Literal["breaking", "crime", "traffic", "weather", "events", "food", "sports",
                   "culture", "community", "business", "politics", "other"]

CATEGORY_LABELS = {
    "breaking": "BREAKING", "crime": "FORT WORTH", "traffic": "TRAFFIC", "weather": "WEATHER",
    "events": "EVENTS", "food": "FOOD & DRINK", "sports": "SPORTS", "culture": "CULTURE",
    "community": "COMMUNITY", "business": "BUSINESS", "politics": "CITY HALL", "other": "FORT WORTH",
}


@dataclass
class Story:
    """One candidate thing to post about, normalized from any source."""

    id: str
    source: str                      # human name of the source ("Fort Worth Report", "National Weather Service")
    source_kind: str                 # rss | nws_alert | nws_forecast | event | event_roundup | reddit
    title: str
    summary: str
    url: str
    published: Optional[datetime] = None
    category_hint: Optional[str] = None
    image_url: Optional[str] = None  # image offered by the source
    image_credit: Optional[str] = None
    image_license: Optional[str] = None  # public-domain | ticketmaster | source-owned | official
    image_policy: str = "none"       # none | source_image  (may we use image_url in our post?)
    official: bool = False           # government / public-domain source
    always_relevant: bool = False
    weight: float = 1.0
    extra: dict = field(default_factory=dict)
    # filled in by filters / ranking
    category: Optional[str] = None
    relevance: int = 0
    score: float = 0.0

    def text(self) -> str:
        return f"{self.title} {self.summary}".lower()

    def age_hours(self, now: datetime) -> float:
        if not self.published:
            return 0.0
        pub = self.published if self.published.tzinfo else self.published.replace(tzinfo=timezone.utc)
        return max(0.0, (now - pub).total_seconds() / 3600.0)

    @property
    def severity(self) -> str:
        return str(self.extra.get("severity", "")).lower()

    @property
    def is_urgent(self) -> bool:
        """Severe weather and breaking news skip the spacing between posts and the quiet hours."""
        local = (self.extra or {}).get("scope", "local") in ("local", "dfw")
        flagged = (self.category or "") == "breaking" or (self.title or "").lower().startswith(("breaking", "developing"))
        return (self.source_kind == "nws_alert" and self.severity in ("severe", "extreme")) or (flagged and local)


class PostCopy(BaseModel):
    """What the caption writer (Claude or the template) produces for a story."""

    skip: bool = Field(default=False, description="true if this story should not be posted")
    skip_reason: str = Field(default="", description="why it was skipped, empty if not skipped")
    category: Category = Field(default="other")
    headline: str = Field(description="<= 110 chars, the one-line news headline printed on the post card, sentence case, no emoji/hashtags, no trailing period")
    caption: str = Field(description="the Facebook caption, hook first, under 500 chars, no hashtags, no URLs")
    first_comment: str = Field(default="", description="source line + photo credit placeholder {photo_credit}")
    hashtags: list[str] = Field(default_factory=list, description="5-8 hashtags like #FortWorth")
    image_query: str = Field(default="Fort Worth skyline", description="2-5 word stock photo query")
    location: str = Field(default="Fort Worth, TX")


@dataclass
class ImageAsset:
    path: Path
    credit: str                 # human credit line, e.g. "Photo: Jane Doe via Pexels"
    license: str                # pexels | wikimedia-cc | public-domain | ticketmaster | official | placeholder | camera
    provider: str               # pexels | wikimedia | nws | ticketmaster | source | camera | placeholder
    source_url: Optional[str] = None
    photo_id: Optional[str] = None
    width: int = 0
    height: int = 0
    subject: Optional[str] = None   # why this photo: "entity:tcu" | "topic:tcu-football" | "beat:police" | "own" (the story's own image)


@dataclass
class PostDraft:
    story: Story
    copy: PostCopy
    writer: str                               # claude | template
    mode: Literal["photo", "link", "share", "video", "text"] = "photo"   # share = a public facebook.com post URL, rendered nested by Facebook
    image: Optional[ImageAsset] = None
    video_path: Optional[Path] = None
    video_url: Optional[str] = None            # public URL of the clip once cycle.sh has uploaded it (release asset)
    story_path: Optional[Path] = None         # the same post as a 1080x1920 Story image
    link: Optional[str] = None                # for link posts
    scheduled_at: Optional[datetime] = None   # None = publish now
    sponsor_line: Optional[str] = None

    def caption_text(self) -> str:
        parts = [self.copy.caption.strip()]
        if self.sponsor_line:
            parts.append(self.sponsor_line.strip())
        return "\n\n".join(p for p in parts if p)

    def first_comment_text(self) -> str:
        text = self.copy.first_comment or ""
        credit = self.image.credit if self.image and self.image.provider not in ("card", "placeholder", "quote") else ""
        text = text.replace("{photo_credit}", credit).strip()
        tags = " ".join(self.copy.hashtags)
        if tags:
            text = (text + "\n\n" + tags).strip()
        return text


@dataclass
class PublishResult:
    ok: bool
    publisher: str
    post_id: Optional[str] = None
    url: Optional[str] = None
    detail: str = ""
