# Go live: exactly what I need to start posting

Page: **Fort Worth Daily** on Facebook, **@fortworthdailytv** on Instagram. The automation is built, tested and pushed.
It cannot post until the items marked **YOU** exist, because they are accounts and keys only the owner can create. Nothing
here costs money: free tiers plus the Claude subscription and the Metricool plan you already have.

## 1. What I need from you (about 45 minutes, once)

| # | Item | Where | What to give me |
|---|---|---|---|
| 1 | **YOU** · Facebook Page and Instagram linked | Meta Business Suite → the Page → Linked accounts | confirmation that @fortworthdailytv is a Business/Creator account linked to the Page |
| 2 | **YOU** · Metricool brand | Metricool → add brand "Fort Worth Daily" → connect Facebook Page + Instagram | the brand's **blog id** (number in the planner URL), your **user id**, and a **user token** (Settings → API) |
| 3 | **YOU** · GitHub repo public + default branch `main` | repo Settings → General | needed so images have public URLs for Metricool and Actions minutes are unlimited (free) |
| 4 | **YOU** · GitHub secrets | repo Settings → Secrets and variables → Actions → Secrets | `METRICOOL_USER_TOKEN`, `METRICOOL_USER_ID`, `METRICOOL_BLOG_ID`, `CLAUDE_CODE_OAUTH_TOKEN` (see §2), `NWS_USER_AGENT` (any identifying text with a contact email) |
| 5 | **YOU** · GitHub variables | same page → Variables | `FTWTV_PUBLISHER = dryrun` to start, `METRICOOL_NETWORKS = facebook,instagram`, `MEDIA_BASE_URL = https://raw.githubusercontent.com/fwagtx/FTWorthTv/main`, `METRICOOL_AUTOPUBLISH = false` if you want one-tap approval on your phone for every post at first |
| 6 | **YOU** · free photo keys (optional but recommended) | unsplash.com/developers, flickr.com/services/apps/create, pixabay.com/api/docs | secrets `UNSPLASH_ACCESS_KEY`, `FLICKR_API_KEY`, `PIXABAY_API_KEY`. Without them Openverse and Wikimedia Commons are used (works, fewer photos) |
| 7 | **YOU** · Ticketmaster key (optional) | developer.ticketmaster.com | secret `TICKETMASTER_API_KEY` for Dickies Arena, Billy Bob's and Texas Live event posts with real artist art |
| 8 | **YOU** · the reference study (optional, makes the voice exact) | docs/REFERENCE_STUDY.md | the JSON from Claude for Chrome |
| 9 | ME · everything else | this repo | I flip the schedule on, watch the first day, and tune sources, caps and captions |

### The Claude token (step 4, two minutes)
On your computer, in a terminal with Claude Code installed: `claude setup-token`. It prints a long token that lets the
workflow write captions through your Pro/Max subscription instead of a paid API key. Paste it as the secret
`CLAUDE_CODE_OAUTH_TOKEN`. Without it the template writer runs (plainer captions, still correct).

## 2. What happens once those exist

1. I run the workflow once with `FTWTV_PUBLISHER = dryrun` and send you the preview page of that run's posts.
2. You flip the variable to `metricool`. With `METRICOOL_AUTOPUBLISH = false`, every post lands in Metricool for your approval;
   with `true`, it publishes itself.
3. The schedule is **hourly** (`.github/workflows/post.yml`), up to 2 posts per run, 12 a day, quiet from 11pm to 6am Central.
   Severe weather bypasses the quiet hours. Wanted bulletins are capped at one a day; the felony arrest log is off.
4. Every post: the two-paragraph summary caption, our card (FWD avatar, Fort Worth Daily, @fortworthdailytv, headline, photo),
   and a first comment with the source link, the photo credit and the presumption-of-innocence line where it applies.
5. After the first week, send me the Page insights export (reach per post) and I tune the mix to what the audience answered.

## 3. What is covered ("everything Fort Worth and beyond")

- **News:** Fort Worth Report, Star-Telegram, FOX 4, NBC 5, WFAA, CBS Texas, Fort Worth Business Press, Fort Worth Magazine,
  Fort Worth Weekly, CultureMap, TCU, City of Fort Worth news, City of Arlington news, Fort Worth police releases.
- **Weather:** National Weather Service alerts, radar and the daily forecast for Tarrant County.
- **Events:** Ticketmaster for Dickies Arena, Billy Bob's, Texas Live and the Stockyards; the culture calendar
  (Stock Show, Juneteenth, Parade of Lights, Main Street Arts Festival, heat and freeze days).
- **Crime:** official wanted bulletins (FWPD, Arlington PD, DPS), never scraped jail records.
- **Beyond:** Arlington and Tarrant County are in by default; the Cowboys, Rangers and Mavericks are in through the DFW
  outlets. To widen further, add keywords to `config/sources.yaml` → `relevance`.
- **Submissions:** the first comment asks for videos and photos. Pick an inbox (Google Form or Page messages) and I wire
  approved submissions into the queue with the "(via IG/ user)" credit.

## 4. Not yet, and why

- **X:** claim @fortworthdaily or @FortWorthDaily when you can; Metricool posts there too once connected.
- **TikTok / Reels:** the pipeline does not produce video yet. Fan clips from the inbox are the way in.
- **Website:** GitHub Pages site generated from the posts, after the socials are running.
