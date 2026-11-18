"""Settings = YAML config (brand + sources) + environment variables (secrets + switches)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml


def find_root(start: Path | None = None) -> Path:
    env = os.environ.get("FTWTV_ROOT")
    if env:
        return Path(env).resolve()
    here = (start or Path.cwd()).resolve()
    for candidate in [here, *here.parents]:
        if (candidate / "config" / "brand.yaml").exists():
            return candidate
    # installed as a package: assume repo layout src/ftworthtv/config.py
    pkg_root = Path(__file__).resolve().parents[2]
    if (pkg_root / "config" / "brand.yaml").exists():
        return pkg_root
    return here


def load_dotenv(path: Path, env: dict | None = None) -> None:
    """Minimal .env loader (KEY=VALUE, # comments). Never overrides variables that are already set."""
    env = os.environ if env is None else env
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in env:
            env[key] = value


def _bool(value: str | None, default: bool = False) -> bool:
    if value is None or value == "":
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


@dataclass
class Settings:
    root: Path
    brand: dict
    sources: dict
    publisher: str = "dryrun"
    dry_run: bool = False
    offline: bool = False                      # demo mode: never touch the network
    out_dir: Path = Path("out")
    state_path: Path = Path("state/posted.json")
    max_posts: int = 2
    since_hours: int = 36
    writer: str = "auto"                       # auto | template | claude_code | claude_api
    claude_code_oauth_token: str | None = None # from `claude setup-token` (Pro/Max subscription), used by headless Claude Code
    anthropic_api_key: str | None = None
    model: str = "claude-opus-5-5"
    effort: str = "medium"
    pexels_api_key: str | None = None
    unsplash_access_key: str | None = None
    flickr_api_key: str | None = None
    pixabay_api_key: str | None = None
    openverse_client_id: str | None = None
    openverse_client_secret: str | None = None
    ticketmaster_api_key: str | None = None
    nws_user_agent: str = "FTWorthTv/0.1 (contact: set NWS_USER_AGENT)"
    fb_page_id: str | None = None
    fb_page_token: str | None = None
    fb_graph_version: str = "v25.0"
    fb_place_id: str | None = None
    fb_app_id: str | None = None
    fb_app_secret: str | None = None
    ig_user_id: str | None = None              # Instagram Business account id linked to the Page (free cross-posting)
    metricool_user_token: str | None = None
    metricool_user_id: str | None = None
    metricool_blog_id: str | None = None
    metricool_networks: list[str] = field(default_factory=lambda: ["facebook"])
    metricool_autopublish: bool = True          # False = Metricool pushes the post to your phone for one-tap approval
    media_base_url: str | None = None
    verbose: bool = False

    # ---- derived helpers -------------------------------------------------
    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.brand.get("timezone", "America/Chicago"))

    @property
    def assets_dir(self) -> Path:
        return self.root / "assets"

    @property
    def fonts_dir(self) -> Path:
        return self.assets_dir / "fonts"

    @property
    def posting(self) -> dict:
        return self.brand.get("posting", {})

    @property
    def relevance(self) -> dict:
        return self.sources.get("relevance", {})

    def hashtags_for(self, category: str | None) -> list[str]:
        tags = self.brand.get("hashtags", {})
        by_cat = tags.get("by_category", {}) or {}
        return list(by_cat.get(category or "", tags.get("default", ["#FortWorth"])))

    def redacted(self) -> dict:
        """Settings as a dict with secrets masked (for `ftworthtv config`)."""
        out = {}
        for k, v in self.__dict__.items():
            if k in ("brand", "sources"):
                continue
            if any(s in k for s in ("key", "token", "secret")) and v:
                v = f"{str(v)[:4]}…({len(str(v))} chars)"
            out[k] = str(v) if isinstance(v, Path) else v
        return out

    # ---- construction ----------------------------------------------------
    @classmethod
    def load(cls, root: Path | None = None, env: dict | None = None, **overrides) -> "Settings":
        root = (root or find_root()).resolve()
        env = os.environ if env is None else env
        load_dotenv(root / ".env", env)
        brand = yaml.safe_load((root / "config" / "brand.yaml").read_text(encoding="utf-8")) or {}
        sources = yaml.safe_load((root / "config" / "sources.yaml").read_text(encoding="utf-8")) or {}

        def pick(name: str, default=None):
            value = env.get(name)
            return value if value not in (None, "") else default

        networks = [n.strip() for n in str(pick("METRICOOL_NETWORKS", "facebook")).split(",") if n.strip()]
        settings = cls(
            root=root,
            brand=brand,
            sources=sources,
            publisher=str(pick("FTWTV_PUBLISHER", "dryrun")).lower(),
            dry_run=_bool(pick("FTWTV_DRY_RUN"), False),
            out_dir=root / str(pick("FTWTV_OUT_DIR", "out")),
            state_path=root / str(pick("FTWTV_STATE_PATH", "state/posted.json")),
            max_posts=int(pick("FTWTV_MAX_POSTS", brand.get("posting", {}).get("max_posts_per_run", 2))),
            since_hours=int(pick("FTWTV_SINCE_HOURS", sources.get("relevance", {}).get("max_age_hours", 36))),
            writer=str(pick("FTWTV_WRITER", "auto")).lower(),
            claude_code_oauth_token=pick("CLAUDE_CODE_OAUTH_TOKEN"),
            anthropic_api_key=pick("ANTHROPIC_API_KEY"),
            model=str(pick("FTWTV_MODEL", "claude-opus-5-5")),
            effort=str(pick("FTWTV_EFFORT", "medium")),
            pexels_api_key=pick("PEXELS_API_KEY"),
            unsplash_access_key=pick("UNSPLASH_ACCESS_KEY"),
            flickr_api_key=pick("FLICKR_API_KEY"),
            pixabay_api_key=pick("PIXABAY_API_KEY"),
            openverse_client_id=pick("OPENVERSE_CLIENT_ID"),
            openverse_client_secret=pick("OPENVERSE_CLIENT_SECRET"),
            ticketmaster_api_key=pick("TICKETMASTER_API_KEY"),
            nws_user_agent=str(pick("NWS_USER_AGENT", "FTWorthTv/0.1 (contact: set NWS_USER_AGENT)")),
            fb_page_id=pick("FB_PAGE_ID"),
            fb_page_token=pick("FB_PAGE_ACCESS_TOKEN"),
            fb_graph_version=str(pick("FB_GRAPH_VERSION", "v25.0")),
            fb_place_id=pick("FB_PLACE_ID"),
            fb_app_id=pick("FB_APP_ID"),
            fb_app_secret=pick("FB_APP_SECRET"),
            ig_user_id=pick("IG_USER_ID"),
            metricool_user_token=pick("METRICOOL_USER_TOKEN"),
            metricool_user_id=pick("METRICOOL_USER_ID"),
            metricool_blog_id=pick("METRICOOL_BLOG_ID"),
            metricool_networks=networks or ["facebook"],
            metricool_autopublish=_bool(pick("METRICOOL_AUTOPUBLISH"), True),
            media_base_url=pick("MEDIA_BASE_URL"),
        )
        for key, value in overrides.items():
            if value is not None:
                setattr(settings, key, value)
        return settings
