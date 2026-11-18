# Go-live checklist: exactly what is needed, in order

Everything below is something only the page owner can do (accounts, keys, approvals). The automation is already built,
tested and pushed; once these are in place it posts by itself.

## A. Five decisions (2 minutes, just answer them)

| # | Decision | Default if you say nothing |
|---|----------|----------------------------|
| 1 | Page name and handles | "Fort Worth Texas TV", Facebook `@FortWorthTexasTV`, Instagram `@FortWorthTexasTV` (check the handle is free) |
| 2 | Posting path | Facebook Graph API directly (free). Metricool instead if you want Instagram in the same post and phone approval |
| 3 | Crime content | WANTED bulletins on (1/day), felony arrest log off, sex-offense cases filtered out |
| 4 | Volume | up to 2 posts per run, 10 per day, quiet 11pm–6am Central |
| 5 | Sponsor line | none until you have a sponsor ("Official partner of …" every 5th post) |

## B. Free keys (15 minutes total) → paste as GitHub secrets

| Secret name | Where to get it | Time | Why |
|---|---|---|---|
| `PEXELS_API_KEY` | pexels.com/api → "Get started" | 2 min | real, well-matched Fort Worth photos instead of Wikimedia luck |
| `TICKETMASTER_API_KEY` | developer.ticketmaster.com → create app → Consumer Key | 5 min | real event/artist images and ticket links for Dickies Arena, Billy Bob's, Texas Live |
| `NWS_USER_AGENT` | nothing to sign up for; just the text `FTWorthTv/0.1 (contact: you@yourdomain.com)` | 0 | the weather service requires an identifying string |
| `ANTHROPIC_API_KEY` | console.anthropic.com → API keys (add $20 of credit) | 5 min | captions in the Dallas voice instead of the template; about a cent a post |

## C. Facebook Page + a token that doesn't expire (20–30 minutes)

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
3. **Variables**: `FTWTV_PUBLISHER = dryrun` (start here), optionally `FTWTV_MAX_POSTS = 2`.
4. Actions → "Post to Fort Worth Texas TV" → Run workflow. Download the artifact, open `latest-preview.html`, check 10 posts.
5. Flip the variable to `facebook` (or `metricool`). Done: it runs every 2 hours.
6. Housekeeping: delete the `renders/*` and `pages/*` branches (sample renders), or tell me to.

## E. Metricool instead of direct Facebook (optional, 10 minutes)

Secrets `METRICOOL_USER_TOKEN`, `METRICOOL_USER_ID`, `METRICOOL_BLOG_ID` (API add-on on your plan), variable `METRICOOL_NETWORKS = facebook,instagram`,
variable `MEDIA_BASE_URL = https://raw.githubusercontent.com/fwagtx/FTWorthTv/main` (repo must be public for Metricool to fetch the images).

## F. The missing ingredient: the inbox (your call on tooling, 30 minutes to set up)

The Dallas page's viral posts are videos people send them. Pick one:
* **Google Form** (fastest): fields = video/photo upload, what happened, where, when, your Instagram handle for credit, consent checkbox.
  Share the responses sheet with me and I'll wire it to `ftworthtv run --stories` with a one-tap "approved" column.
* **Page inbox** (Messenger) via Meta webhooks: needs `pages_messaging` and a small receiver; more work, more natural for followers.
Either way the first comment already says "DM us your videos & photos 📲" and the caption credit "(via IG/ user)" is built.

## G. First week

Run with `dryrun` for a day, then `facebook`. After two weeks, send me the Page insights export and I'll tune caps, hooks and sources
to what got reach.
