# FTWorthTv — "Fort Worth Texas TV", fully automated

A hands-off Fort Worth, Texas local news & entertainment page for Facebook (and Instagram), built to look and feel like
[Dallas Texas TV](https://www.facebook.com/DallasTexasTV) but for Fort Worth / Tarrant County.

Every two hours a GitHub Actions job:

1. **collects** what is happening in Fort Worth from public feeds and APIs (local outlets, city hall, police, National Weather
   Service, Ticketmaster events, optional Reddit and traffic cameras),
2. **filters and ranks** it (is it really Fort Worth? fresh? brand-safe? what kind of story?),
3. **writes the caption** in the Dallas-Texas-TV voice (Claude, with a no-AI template fallback),
4. **gets a real photo** it is allowed to post (licensed stock of Fort Worth, government/public-domain imagery, event promo images,
   live traffic cameras) and renders the branded card with the headline overlay,
5. **publishes** (photo post + hashtags/source in the first comment, spaced out, quiet hours, daily cap) through the Facebook Graph
   API or Metricool, and
6. **remembers** what it posted so nothing repeats.

`ftworthtv preview` shows exactly what a run produces, with no keys and no network, in `out/latest-preview.html`.

---

## Is it possible / achievable? Short answer: yes, with two honest caveats

**What I found about the Dallas page.** Dallas Texas TV (~647K followers, bio "The home of DTX entertainment · All news available",
"official partner of J. Alexander Law") is an *entertainment-first* local page. Its posts are short, punchy captions
("635 Today", "Downtown Dallas, how does this happen 😂", "Kid Cudi joins Kanye at AT&T") on top of a real photo or, more often, a
phone video of something happening in DFW: concerts at AT&T Stadium, wrecks on 635, street scenes, viral moments, sports. Links and
credits stay out of the caption, Instagram is cross-promoted ("Full video on our Instagram @DallasTexasTV"), and a sponsor line rides
on some posts. The photos and videos come from three places: **people who DM them**, **reposts of other accounts/outlets**, and
**public sources** (weather, traffic cams, event promo material).

**What this repo automates 100 %:**

| Dallas-page ingredient | FTWorthTv equivalent | Fully automatic? |
|---|---|---|
| Breaking local news, crime, traffic, food, culture, business | 13 Fort Worth feeds (Fort Worth Report, Star-Telegram, CultureMap, Weekly, FW Magazine, FOX 4, NBC 5, WFAA, CBS Texas, City of Fort Worth, FWPD, TCU) | ✅ |
| Weather alerts ("Tornado warning for Tarrant County") | NWS alerts for zone TXZ118 + real radar image (public domain) | ✅ no key needed |
| "Good morning DFW" forecast post | NWS daily forecast at 7 am Central | ✅ no key needed |
| Concerts / rodeo / Dickies Arena / Billy Bob's | Ticketmaster Discovery API: real event images + ticket links, Thursday "This weekend in Fort Worth" roundup | ✅ free key |
| "635 Today" traffic pics | Traffic story + matching TxDOT camera snapshot (LIVE photo) | ✅ once you paste camera URLs |
| Captions in their voice, emoji, 📍 location, "Follow us" CTA | Claude writer with brand voice + guardrails (never invents facts, skips unsafe stories) or template writer | ✅ |
| Real photos on every post | Unsplash / Flickr CC / Pixabay / Pexels (any free key) or Openverse + Wikimedia Commons (no key) photos of Fort Worth; NWS radar; event images | ✅ |
| Hashtags + source link in first comment, posts spaced out, quiet hours, daily cap, no repeats | built in | ✅ |
| Sponsor line every Nth post | `sponsor:` in `config/brand.yaml` | ✅ |
| Mugshot / WANTED posts like the DFW crime pages | FWPD Most Wanted, Arlington PD "Cash for Crooks", Texas DPS 10 Most Wanted: the agency's own photo, charge, Crime Stoppers reward + tip line | ✅ no key needed |
| "Fort Worth arrests" lists | FWPD public arrest log → daily felony-bookings roundup (names, ages, charges; no photos) | ✅ off by default |
| City hall / police releases with their photos | OpenCities listings of fortworthtexas.gov, police.fortworthtexas.gov, arlingtontx.gov (no RSS, parsed from HTML, release page fetched for the photo) | ✅ |
| Posting to Facebook (+ Instagram) | Graph API publisher, or Metricool publisher (you already use Metricool) | ✅ |

**Caveat 1 — the viral phone videos.** The Dallas page's biggest hits are crowd-sourced clips (a fight outside AT&T Stadium, a car
flying off the High Five). No pipeline can film those. They can only be *semi*-automated: a submissions inbox (Page DMs, an email
address or a Google Form) that a human approves in seconds. Everything around it (crediting, captioning, scheduling) is already
handled here, and it is the first item on the roadmap below.

**Caveat 2 — other people's photos.** Downloading a news outlet's photo and reposting it as your own native photo (what many of
these pages quietly do) is copyright infringement and the fastest way to get a page restricted. So for outlet stories this repo
either (a) posts a licensed photo of Fort Worth with the headline on it and credits the outlet in the first comment (default,
looks like the Dallas page), or (b) posts a *link post* so Facebook shows the outlet's own photo legally (`news_photo_mode: link`,
safer, lower reach). Government and NWS imagery and Ticketmaster event images are fine to use natively, and that is what the
pipeline prefers when a story has them.

Bottom line: a page that posts 6–10 real, local, photo-backed posts a day with zero human touch is achievable with this repo
today. Matching the Dallas page's *virality* additionally needs a human-curated video inbox.

### Mugshots: where the DFW pages get them, and what this repo does

The DFW crime pages run booking photos from three places: (1) police press releases and police social posts, (2) the county
jail's inmate lookup (booking photos are public records in Texas), and (3) TV-station stories that got them from (1) or (2).
Fort Worth PD does **not** put photos in its public arrest log (names, ages, charges only), and its release pages are taken
down after a while, so the reliable, no-questions-asked source is the **WANTED** material every agency publishes to be shared:

* `sources/wanted.py` parses FWPD's Most Wanted page, Arlington PD's Cash-for-Crooks fugitives and Texas DPS's 10 Most Wanted
  (DPS filtered to notices that mention Tarrant County). Each person becomes one post: the agency's photo on a blurred backdrop
  (never cropped), "WANTED" label, charge, Crime Stoppers reward and the 817-469-TIPS line. Juveniles are skipped, the agency is
  credited on the card and in the first comment, and the first comment carries the presumption-of-innocence disclaimer from
  `config/brand.yaml`. At most one WANTED post per run (`wanted.max_per_run`).
* `sources/arrests.py` turns FWPD's public arrest log into a daily "felony bookings" roundup (off by default: it names people
  who have only been accused).
* Photos from police *press releases* are used automatically when a release carries one (`sources/article.py` fetches the
  release page and takes the og:image / first body image).
* Jail-lookup scraping is deliberately **not** implemented. Texas Bus. & Com. Code ch. 109 regulates commercial mugshot
  publication and requires correction/removal when charges are dropped or the person is acquitted; the brand-safety blocklist
  in `config/sources.yaml` also keeps sexual-assault and child-victim cases off the page. Honor removal requests.

Preview just this material with `ftworthtv run --dry-run --only-kinds wanted,arrest_log` (or the "Render sample posts"
workflow with `only_kinds`).

---

## Two looks: "dallas" (default) and "detailed"

`config/brand.yaml` has two switches that decide how a post looks:

* `caption.style: dallas` — one or two plain sentences, present tense, no hashtags, no bullet points, no 📍 line, at most one
  emoji (🚨 for incidents, 😂 for funny moments), then `Follow us on Instagram @FortWorthTexasTV`. That is how the Dallas page
  writes ("Kid Cudi joins Kanye at AT&T", "Things got heated between Cowboys and 49ers fans at Texas Live during the game.
  Arlington police responded to the scene. 🚨"). `detailed` is the hook / facts / 📍 / CTA format.
* `card.style: plain` — the photo as-is at its own aspect ratio with a small `@FortWorthTexasTV` watermark, no headline overlay,
  no badge, exactly like the Dallas page's media. A story without a usable photo becomes a link post instead of a fake graphic.
  `headline` is the branded 1080×1350 card with the headline on the photo (useful for stories where the photo is generic).

Source credit, photo credit and the presumption-of-innocence line stay in the first comment in both styles.

## What a run produces

`ftworthtv preview --max 4` (offline demo data) gives, in ~2 seconds:

```
run 20261119-173000: 17 candidates, 4 post(s)
  OK  [weather] Severe Thunderstorm Warning: Tarrant, TX
  OK  [events]  This weekend in Fort Worth
  OK  [traffic] Crash shuts down northbound I-35W near downtown Fort Worth during morning rush
  OK  [sports]  Example Rodeo Night at Cowtown Coliseum
```

and for every post a folder with `card.jpg` (1080×1350 branded photo card), `caption.txt`, `first_comment.txt` and `post.json`,
plus `preview.html`, a Facebook-feed-looking page to eyeball before going live. Example caption (template writer):

```
⚠️ Severe Thunderstorm Warning for Tarrant, TX until 7:30 PM

For your protection move to an interior room on the lowest floor of a building. Stay away from windows.

Stay safe out there, Fort Worth 💜

Follow @FortWorthTexasTV for more 📲
```
first comment: `Source: National Weather Service <link> · Radar: NWS Fort Worth (public domain) · #FortWorth #FortWorthWeather #DFWwx #TXwx #Texas`

In the offline demo the photo is a generated skyline placeholder. With a free Pexels key the same card carries a real photo of
Fort Worth; weather posts carry the real NWS radar; event posts carry the promoter's event image.

---

## Quick start

```bash
git clone https://github.com/fwagtx/FTWorthTv && cd FTWorthTv
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest -q                      # 31 tests
ftworthtv preview --max 4      # offline demo -> out/latest-preview.html
cp .env.example .env           # add keys (see docs/SETUP.md)
ftworthtv sources check        # verify every RSS feed from YOUR network (some are marked verify: true)
ftworthtv run --dry-run        # real sources, real photos, nothing posted
ftworthtv run --dry-run --only-kinds wanted,arrest_log      # preview one kind of content
ftworthtv run --dry-run --stories examples/real/headlines-2026-11-17.json --no-sources   # render from a JSON of headlines
ftworthtv run                  # posts via FTWTV_PUBLISHER (dryrun | facebook | metricool)
```

Full setup (Facebook token that never expires, Metricool, keys, GitHub secrets, go-live checklist): **[docs/SETUP.md](docs/SETUP.md)**.
What the Dallas page posts, pillar by pillar, and how each pillar is sourced for Fort Worth: **[docs/CONTENT_PLAYBOOK.md](docs/CONTENT_PLAYBOOK.md)**.
Exactly what the owner must provide to go live, in order: **[docs/GO_LIVE.md](docs/GO_LIVE.md)**.

---

## How it works

```
config/sources.yaml  ──►  sources/   rss · nws · ticketmaster · reddit · cameras      (collect)
                                │
                           filters.py   local? fresh? brand-safe? category            (filter)
                           ranking.py   relevance × source weight × freshness × urgency (rank + diversity)
                                │
                           writer.py    Claude (structured output) ──or── template      (caption, headline,
                                │                                                        hashtags, image query)
                           images/      providers.py  Pexels / Wikimedia (licensed)      (real photo)
                                        + NWS radar / Ticketmaster image / TxDOT cam
                                        card.py       1080×1350 card: photo + headline + FTW TV badge + credits
                                │
                           publishers/  facebook.py (Graph API)  metricool.py  dryrun.py (publish)
                                │
                           state/posted.json   dedupe memory, daily counts, used photos  (remember)
```

Everything is configuration:

* `config/brand.yaml` — page name/handle, voice notes for the writer, hashtags per category, colors, card size, posting cadence
  (`max_posts_per_run`, `min_minutes_between_posts`, `daily_cap`, `quiet_hours_local`, `news_photo_mode`), sponsor line.
* `config/sources.yaml` — every feed/API, per-source weight and image policy, NWS zone/radar, Ticketmaster venues, Reddit, traffic
  cameras, Fort Worth keyword list, blocklist, excluded categories (politics by default, like the Dallas page).

### The caption writer (three backends, all optional)

1. **Claude Code with your Pro/Max subscription (free with the subscription).** Run `claude setup-token` once on your computer,
   store the token as the `CLAUDE_CODE_OAUTH_TOKEN` secret, and the workflow installs Claude Code and asks it for each caption
   headlessly (`claude -p … --output-format json`). No pay-as-you-go API bill; ten posts a day is a rounding error on the plan.
2. **Anthropic API** (`ANTHROPIC_API_KEY`, pay-as-you-go, about a cent per post) — same prompt through the SDK with structured output.
3. **Template writer** — deterministic, free, no network. Used automatically whenever 1 and 2 are unavailable, so a run never
   fails because of the AI. Every sample in this README came from it.

`FTWTV_WRITER` = `auto` (default order above) | `template` | `claude_code` | `claude_api`. The prompt carries the brand voice and
hard rules (never invent facts, Dallas-style one or two sentences, no hashtags, kind-specific rules for alerts, events, WANTED).

### Photos, legally

| Story type | Photo | License |
|---|---|---|
| NWS alert | Latest KFWS radar image (`radar.weather.gov`) | public domain |
| Forecast | Licensed Fort Worth skyline photo | Unsplash / Flickr CC / Pixabay / Openverse |
| Ticketmaster event | Event/artist image from the Discovery API, linked to tickets | API terms (promotional use) |
| City of Fort Worth / FWPD release | Their photo (`image_policy: source_image`), credited | government release |
| Traffic story with a matching camera | Live TxDOT snapshot | public |
| Any other outlet story | Licensed photo matching the writer's `image_query`, outlet credited in the first comment, or a link post | Unsplash / Flickr CC / Pixabay / Openverse |

Photographer credit is printed on the card and in the first comment. Recently used photos are remembered so the feed does not
look repetitive. No AI-generated imagery is used anywhere.

### Posting

* **facebook** — `POST /{page}/photos` (or `/feed` for link posts, `/videos` for the optional radar video), then the first comment
  with the source + hashtags. Multiple posts in one run are *scheduled* (`scheduled_publish_time`) ~75 min apart instead of landing
  together. Optional `FB_PLACE_ID` location-tags every post. `ftworthtv fb-token` turns a Graph Explorer user token into a Page
  token that does not expire. No App Review is needed to post to a Page you admin.
* **Instagram (free)** — set `IG_USER_ID` (the Instagram Business account linked to the Page) and `MEDIA_BASE_URL`; the facebook
  publisher then cross-posts each photo through the Instagram Graph API (`/media` → `/media_publish`). The workflow commits the
  images first so they have a public URL on `raw.githubusercontent.com` (public repo).
* **metricool** — schedules Facebook + Instagram (and more) in one call through Metricool's API, with
  `METRICOOL_AUTOPUBLISH=false` for one-tap approval from the Metricool app. No Meta developer app or Page token needed.
* **dryrun** — writes everything to `out/` and nothing leaves the machine. The GitHub workflow always runs phase 1 as a dry run and
  only then publishes (`ftworthtv publish latest`), so you can also insert a human review step between the two.

### Scheduling

`.github/workflows/post.yml` runs every 2 hours (UTC), `sources-check.yml` tests every feed weekly, `tests.yml` runs the test
suite and an offline preview on every push. Quiet hours (11 pm–6 am Central), the daily cap and spacing live in `brand.yaml`;
severe weather always posts. The run output (cards, captions, preview) is uploaded as a workflow artifact for 14 days and the
dedupe memory `state/posted.json` is committed back by the bot.

---

## What was verified, and what you need to check

Built and tested in a sandbox that could not reach the public internet beyond package registries, so:

* ✅ Unit + end-to-end offline tests pass (`pytest`), the demo run renders cards and the preview page, both publishers are tested
  against mocked HTTP, the Claude call uses the current SDK (`anthropic` 2.x, structured outputs).
* ⚠️ Feed URLs marked `verify: true` in `config/sources.yaml` (Star-Telegram, Weekly, FW Magazine, Business Press, WFAA, CBS Texas,
  City of Fort Worth, FWPD, TCU) were taken from directories, not fetched. Run `ftworthtv sources check` once; delete or fix the
  ones that fail. Fort Worth Report, CultureMap, FOX 4 and NBC 5 are standard feeds.
* ⚠️ Live calls to NWS, Pexels, Wikimedia, Ticketmaster, Facebook and Metricool follow their published APIs but were not exercised
  from here. `ftworthtv run --dry-run` with your keys is the first real test, it costs nothing and posts nothing.
* ⚠️ Metricool's request body mirrors the schema of Metricool's own scheduling tool; if their API rejects a field, the error is
  printed verbatim.
* The Dallas page itself could not be opened from the sandbox (facebook.com was blocked); its description above comes from search
  results, its own post titles and its other profiles.

## What it costs

Nothing. Public GitHub repo = unlimited Actions minutes; NWS, Ticketmaster, Openverse, Wikimedia, Unsplash, Flickr, Pixabay and
the Facebook/Instagram Graph APIs are free; captions come from Claude Code on a Pro/Max subscription or from the free template
writer. Metricool is optional (handy if you already have it); the Anthropic pay-as-you-go API is optional and off by default.

## Roadmap (not built yet)

1. **Submissions inbox** → the missing "viral video" ingredient: Page DMs via the Messenger API (or an email/Google Form) → Claude
   vision screens for safety → one-tap approve → auto-credit "📸 via @user". The posting half already exists.
2. **Instagram Reels** (video) — photo cross-posting is built; Reels need the resumable video upload.
3. **Weather Reels** — `weather_radar_video: true` already turns the NWS radar loop into an MP4; needs `publish_video` on the token.
4. **Fort Worth open data** — weekly crime map / restaurant inspection cards from `data.fortworthtexas.gov`.
5. **Engagement loop** — read insights, learn the best hours per category, auto-tune `brand.yaml`.

## Repo layout

```
config/            brand.yaml, sources.yaml
src/ftworthtv/     pipeline.py cli.py writer.py filters.py ranking.py state.py queue.py examples.py
                   sources/ (rss, opencities, article, nws, ticketmaster, wanted, arrests, reddit, cameras)
                   images/ (providers, card, fetch, video)  publishers/ (facebook, metricool, dryrun)
examples/          demo stories used by `ftworthtv preview` and the tests (made up), examples/real/ = real headlines for renders
scripts/           fetch_pages.py (dev helper: fetch public agency pages for inspection, honors robots.txt)
assets/fonts/      Liberation Sans (OFL) so cards render identically everywhere; drop a logo.png in assets/ to replace the badge
state/             posted.json memory (committed by the workflow)
out/               run output (ignored by git)
.github/workflows/ post.yml (every 2h), sources-check.yml (weekly), tests.yml, render.yml (sample posts with real photos,
                   pushed to a renders/ branch), fetch-pages.yml (dev helper)
docs/SETUP.md      keys, Facebook token, Metricool, GitHub secrets, go-live checklist
```
