# Setup: from zero to a page that posts by itself

Time needed: about an hour, most of it clicking through Meta's developer site.

## 1. Run it locally first (10 min)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
ftworthtv preview --max 4          # no keys, no network: renders 4 demo posts into out/
open out/latest-preview.html       # (xdg-open on Linux, start on Windows)
```

Then copy `.env.example` to `.env` and fill in keys as you get them. `ftworthtv config` shows what is set (secrets masked).

## 2. Free keys that make the photos real (15 min)

| Key | Where | Why |
|---|---|---|
| `UNSPLASH_ACCESS_KEY` | https://unsplash.com/developers (instant) | sharp licensed photos; we credit "Photo: Name on Unsplash" and register the download as their API asks |
| `FLICKR_API_KEY` | https://www.flickr.com/services/apps/create (instant) | Creative Commons photos; the deepest local coverage |
| `PIXABAY_API_KEY` | https://pixabay.com/api/docs/ (instant) | backup pool |
| `PEXELS_API_KEY` | https://www.pexels.com/api/ | only if you already have one: new keys were paused in Nov 2026 |
| none | Openverse + Wikimedia Commons | used automatically with no key; Openverse rate-limits anonymous use, so add a key above for a busy page |
| `TICKETMASTER_API_KEY` | https://developer.ticketmaster.com/ (instant, 5 000 calls/day) | concerts, rodeo, TCU, Dickies Arena with event images and ticket links |
| `NWS_USER_AGENT` | nothing to sign up for | the National Weather Service only asks that you identify your app, e.g. `FTWorthTv/0.1 (contact: you@example.com)` |
| `CLAUDE_CODE_OAUTH_TOKEN` | run `claude setup-token` in Claude Code on your computer (Pro/Max subscription) | optional, free with the subscription: Claude writes the captions in the Dallas-Texas-TV voice. Without it the template writer is used. (`ANTHROPIC_API_KEY` is the pay-as-you-go alternative; not needed.) |

Now a real dry run against the live sources:

```bash
ftworthtv sources check      # every RSS feed: items, images, newest date. Delete/fix failing ones in config/sources.yaml.
ftworthtv run --dry-run      # real stories, real photos, real captions -> out/, nothing posted
```

Look at `out/latest-preview.html`. Tune `config/brand.yaml` (voice, hashtags, cadence) and `config/sources.yaml` (weights,
keywords) until you like what you see. This loop is where the page's personality gets made.

## 3. The Facebook Page and a token that never expires (20 min)

1. Create the Page (Meta Business Suite → Pages → Create). Suggested: name **Fort Worth Daily**, category *Media/News Company*,
   username `@FortWorthDaily`, bio from `config/brand.yaml`. Make yourself an admin.
2. Create a Meta app at https://developers.facebook.com/apps → *Create app* → type **Business** (or "Other → Business"). Note the
   **App ID** and **App Secret** (Settings → Basic). The app can stay in **Development mode** forever: that only limits who can
   use it (people with a role in the app), not what the Page can publish, and no App Review is needed to post to a Page you admin.
3. Open the Graph API Explorer: https://developers.facebook.com/tools/explorer/
   * select your app, *User Token*, and add permissions: `pages_show_list`, `pages_read_engagement`, `pages_manage_posts`,
     `pages_manage_engagement` (first comment), `pages_manage_metadata`; add `publish_video` if you want radar Reels.
   * *Generate Access Token*, approve, copy the short-lived user token (valid ~1 h).
4. Turn it into a permanent Page token:

   ```bash
   FB_APP_ID=... FB_APP_SECRET=... ftworthtv fb-token --user-token "EAAB..."
   ```

   It prints `FB_PAGE_ID` and `FB_PAGE_ACCESS_TOKEN` for every Page you admin. Page tokens derived from a long-lived user token do not
   expire (unless you change your password, lose the Page role or revoke the app). Put both in `.env` / GitHub secrets.
   Verify with `ftworthtv run --publisher facebook --max 1` and delete the test post if you like.
5. Optional: `FB_PLACE_ID` tags every post with a location. Find Fort Worth's Place ID by searching `/search?type=place&q=Fort Worth, Texas`
   in the Explorer, or leave it empty.

## 4. Instagram for free, or Metricool (optional, paid add-on)

Free route: make the repo public, link an Instagram Business account to the Page, add `instagram_basic` + `instagram_content_publish`
to the token, set `IG_USER_ID` and `MEDIA_BASE_URL=https://raw.githubusercontent.com/<owner>/<repo>/<branch>`. The facebook publisher
cross-posts every photo. The rest of this section is only for people who already pay for Metricool's API add-on.

1. Add a brand in Metricool for the new Page and connect Facebook (and Instagram Business).
2. Metricool's API needs the API add-on (Advanced/Custom plans). Settings → API → **user token**. Your `userId` is the number in
   the app URL; the brand's `blogId` is in the planner URL or from `https://app.metricool.com/api/admin/simpleProfiles?userId=<id>`.
3. `.env`: `FTWTV_PUBLISHER=metricool`, `METRICOOL_USER_TOKEN`, `METRICOOL_USER_ID`, `METRICOOL_BLOG_ID`, `METRICOOL_NETWORKS=facebook,instagram`.
4. Metricool downloads media from public URLs. The workflow commits each run's cards and serves them from GitHub:
   `MEDIA_BASE_URL=https://raw.githubusercontent.com/<owner>/<repo>/<default-branch>` (the repo must be public, or host the cards
   anywhere else that gives you a public URL and set that base). Locally use `ftworthtv run --dry-run`, push, then
   `ftworthtv publish latest --publisher metricool`.

Want to approve every post from your phone instead of full auto? Set `"autoPublish": False` in `src/ftworthtv/publishers/metricool.py`
(Metricool then sends the post to its mobile app for one-tap publishing).

## 5. Let GitHub run it (10 min)

1. Push this repo. Scheduled workflows only run from the **default branch** (`main`); merge there.
2. Settings → Secrets and variables → Actions:
   * **Variables**: `FTWTV_PUBLISHER=dryrun` (start here!), optionally `FTWTV_MAX_POSTS`, `MEDIA_BASE_URL`, `FB_PLACE_ID`, `FTWTV_MODEL`.
   * **Secrets**: `FB_PAGE_ID`, `FB_PAGE_ACCESS_TOKEN`, `ANTHROPIC_API_KEY`, `PEXELS_API_KEY`, `TICKETMASTER_API_KEY`, `NWS_USER_AGENT`,
     and for Metricool `METRICOOL_USER_TOKEN`, `METRICOOL_USER_ID`, `METRICOOL_BLOG_ID`.
3. Actions → *Post to Fort Worth Daily* → *Run workflow*. Download the `run-N` artifact and open `latest-preview.html`.
4. Happy? Set `FTWTV_PUBLISHER=facebook` (or `metricool`). From then on it runs every two hours, posts up to `max_posts_per_run`
   per run, at most `daily_cap` per day, never between 11 pm and 6 am Central (severe weather excepted), and commits
   `state/posted.json` so nothing repeats.

## 6. Go-live checklist

- [ ] `ftworthtv sources check` is green (or the failing feeds are removed)
- [ ] a dry run looks right in `latest-preview.html`: captions factual, photos sensible, credits present
- [ ] Page bio, profile picture and cover set; `handle` in `brand.yaml` matches the real username
- [ ] `quiet_hours_local`, `daily_cap`, `news_photo_mode` set the way you want (`card` = native photo look, `link` = safest)
- [ ] sponsor line configured or `enabled: false`
- [ ] workflow ran once with `dryrun` on GitHub and the artifact looked right
- [ ] `FTWTV_PUBLISHER` switched to `facebook`/`metricool`; first live run checked on the Page

## Troubleshooting

* **`OAuthException 190`** — token expired/invalid: regenerate with `ftworthtv fb-token`.
* **`(#200) ... pages_manage_posts`** — the token was generated without that permission, or the user lost the Page admin role.
* **Nothing posted, note "too soon since the last post"** — spacing rule; lower `min_minutes_between_posts` or wait.
* **Same photo keeps coming back** — Pexels has few results for that `image_query`; the writer's queries are in `writer.py`
  (`TOPIC`/template defaults) and Claude varies them when a key is set.
* **A feed changed its URL** — `sources-check.yml` fails on Monday; fix the URL in `config/sources.yaml`.
* **Metricool rejects a field** — the exact error is printed; the body is built in `publishers/metricool.py`.
