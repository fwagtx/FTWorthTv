# Go-live checklist: exactly what is needed, in order

Everything below is something only the page owner can do (accounts, keys, approvals). The automation is already built,
tested and pushed; once these are in place it posts by itself. **Nothing here costs money**: every account is a free tier and
the captions use the Claude subscription you already have.

## A. Five decisions (2 minutes, just answer them)

| # | Decision | Default if you say nothing |
|---|----------|----------------------------|
| 1 | Page name and handles | "Fort Worth Texas TV", Facebook `@FortWorthTexasTV`, Instagram `@FortWorthTexasTV` (check the handle is free) |
| 2 | Posting path | **Metricool** (you already have it): Facebook + Instagram from one brand, optional phone approval, no Meta developer app needed. Facebook Graph API direct is the fallback. |
| 3 | Crime content | WANTED bulletins on (1/day), felony arrest log off, sex-offense cases filtered out |
| 4 | Volume | up to 2 posts per run, 10 per day, quiet 11pm–6am Central |
| 5 | Sponsor line | none until you have a sponsor ("Official partner of …" every 5th post) |

6. **Logo** — replace `assets/logo.png` with the real page logo (square PNG). It is the avatar on every post card
   (`card.style: tweet`, the Dallas look: our logo + name + handle, one headline line, the photo). Turn on
   `card.verified_badge` only once Meta verifies the page.

## B. Free keys (15 minutes total) → paste as GitHub secrets

| Secret name | Where to get it | Time | Why |
|---|---|---|---|
| `UNSPLASH_ACCESS_KEY` | unsplash.com/developers → New Application → Access Key | 3 min | sharp, well-matched photos; first choice now that Pexels paused new keys |
| `FLICKR_API_KEY` | flickr.com/services/apps/create → Apply for a non-commercial key | 3 min | Creative Commons photos with the deepest Fort Worth coverage (Stockyards, TCU, Dickies Arena, concerts) |
| `PIXABAY_API_KEY` | pixabay.com → sign up → pixabay.com/api/docs shows your key | 2 min | backup pool, no attribution required |
| (none) | Openverse and Wikimedia Commons | 0 | already used automatically when no key is set |
| `TICKETMASTER_API_KEY` | developer.ticketmaster.com → create app → Consumer Key | 5 min | real event/artist images and ticket links for Dickies Arena, Billy Bob's, Texas Live |
| `NWS_USER_AGENT` | nothing to sign up for; just the text `FTWorthTv/0.1 (contact: you@yourdomain.com)` | 0 | the weather service requires an identifying string |
| `CLAUDE_CODE_OAUTH_TOKEN` | on your computer, in Claude Code: `claude setup-token` (uses your Pro/Max subscription, no API bill) | 2 min | captions in the Dallas voice instead of the template. Each caption is one short headless Claude Code call (about 40K tokens of plan usage, well under a Max plan's daily allowance at 10 posts a day) |

## C1. Metricool path (15 minutes) — recommended, you already pay for it

1. Create the Facebook Page (name from A1) and the Instagram Business account; link them.
2. In Metricool, add a new brand for the page and connect Facebook + Instagram to it.
3. Metricool → Settings → API: copy your **user token**. Your **user id** is the number in the Metricool URL / the one your
   other brands use. The new brand's **blog id** is in the planner URL (or `https://app.metricool.com/api/admin/simpleProfiles?userId=<id>`).
4. GitHub secrets: `METRICOOL_USER_TOKEN`, `METRICOOL_USER_ID`, `METRICOOL_BLOG_ID`.
   Variables: `FTWTV_PUBLISHER = metricool`, `METRICOOL_NETWORKS = facebook,instagram`,
   `MEDIA_BASE_URL = https://raw.githubusercontent.com/fwagtx/FTWorthTv/main` (repo public), and
   `METRICOOL_AUTOPUBLISH = false` if you want every post sent to your phone for one-tap approval first.
5. That's it: no Meta app, no tokens. Skip C2 unless you want the direct path later.

## C2. Facebook Graph API direct (fallback, 20–30 minutes)

1. Create the Page in Meta Business Suite (name from A1). Make yourself admin. Add profile picture, cover, bio from `config/brand.yaml`.
2. developers.facebook.com → My Apps → Create app → type **Business**. Note App ID and App Secret (Settings → Basic). Leave the app in Development mode; no App Review is needed to post to your own Page.
3. Graph API Explorer (developers.facebook.com/tools/explorer): pick the app → User Token → add permissions
   `pages_show_list, pages_read_engagement, pages_manage_posts, pages_manage_engagement, pages_manage_metadata` → Generate Access Token.
4. Make it permanent, two ways:
   * **No code:** Access Token Tool (developers.facebook.com/tools/accesstoken) → Debug → **Extend Access Token** (60-day user token) → back in the Explorer, with that token run `GET /me/accounts` → copy the Page's `access_token` and `id`. Page tokens obtained from a long-lived user token do not expire.
   * **With Python:** `pip install -e . && FB_APP_ID=… FB_APP_SECRET=… ftworthtv fb-token --user-token "EAAB…"` prints the same two values.
5. Paste as secrets `FB_PAGE_ID` and `FB_PAGE_ACCESS_TOKEN`. Optional variable `FB_PLACE_ID` (Fort Worth place id) to location-tag posts.

## D. GitHub (10 minutes)

1. Settings → General → Default branch: rename `claude/practical-mccarthy-mi4jkw` to `main` (or tell me to push `main`). Scheduled workflows run from the default branch only.
2. Settings → Secrets and variables → Actions → **Secrets**: everything from B and C.
3. **Variables**: `FTWTV_PUBLISHER = dryrun` (start here), optionally `FTWTV_MAX_POSTS = 2`. Flip to `metricool` (or `facebook`) in step 5.
4. Actions → "Post to Fort Worth Texas TV" → Run workflow. Download the artifact, open `latest-preview.html`, check 10 posts.
5. Flip the variable to `metricool` (or `facebook`). Done: it runs every 2 hours.
6. Housekeeping: delete the `renders/*` and `pages/*` branches (sample renders), or tell me to.

## E. Instagram without Metricool (only for the C2 path, 10 minutes)

1. Make the repo **public** (Settings → General → Danger zone → Change visibility). That also gives unlimited free Actions minutes.
2. Convert the Instagram account to Business/Creator and link it to the Page.
3. When generating the token in C2, also tick `instagram_basic` and `instagram_content_publish`.
4. Find the Instagram account id: Graph API Explorer → `GET /{page-id}?fields=instagram_business_account`.
5. Variables: `IG_USER_ID = <that id>`, `MEDIA_BASE_URL = https://raw.githubusercontent.com/fwagtx/FTWorthTv/main`.
   Photos whose aspect ratio Instagram rejects (taller than 4:5) are skipped on Instagram and still posted on Facebook.

## F. The missing ingredient: the inbox (your call on tooling, 30 minutes to set up)

The Dallas page's viral posts are videos people send them. Pick one:
* **Google Form** (fastest): fields = video/photo upload, what happened, where, when, your Instagram handle for credit, consent checkbox.
  Share the responses sheet with me and I'll wire it to `ftworthtv run --stories` with a one-tap "approved" column.
* **Page inbox** (Messenger) via Meta webhooks: needs `pages_messaging` and a small receiver; more work, more natural for followers.
Either way the first comment already says "DM us your videos & photos 📲" and the caption credit "(via IG/ user)" is built.

## G. First week

Run with `dryrun` for a day, then `facebook`. After two weeks, send me the Page insights export and I'll tune caps, hooks and sources
to what got reach.
