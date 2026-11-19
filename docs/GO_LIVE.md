# Go live: where things stand and what is still needed

Page: **Fort Worth Daily** on Facebook, **@fortworthdailytv** on Instagram, both connected to the Metricool brand
(brand id 8208939, timezone America/Chicago). The first posts were scheduled through Metricool on Nov 18-19, 2026.
Nothing here costs money: free tiers plus the Claude subscription and the Metricool plan you already have.

## 1. Still needed for the schedule to run on its own (about ten minutes, once)

The GitHub workflow `.github/workflows/post.yml` already runs every 30 minutes on the default branch
(`claude/practical-mccarthy-mi4jkw`) in dry-run mode. It starts publishing the moment these exist:

| # | Where | What |
|---|---|---|
| 1 | Metricool → Settings (gear) → **API** | copy the **user token** |
| 2 | GitHub repo → Settings → Secrets and variables → Actions → **Secrets** | `METRICOOL_USER_TOKEN` = that token · `METRICOOL_USER_ID` = `5456294` · `METRICOOL_BLOG_ID` = `8208939` |
| 3 | same page → **Variables** | `FTWTV_PUBLISHER` = `metricool` · `MEDIA_BASE_URL` = `https://raw.githubusercontent.com/fwagtx/FTWorthTv/claude/practical-mccarthy-mi4jkw` |
| 4 | optional, better captions | secret `CLAUDE_CODE_OAUTH_TOKEN` from `claude setup-token` on your computer (uses your Claude subscription; without it the template writer runs) |
| 5 | optional | variable `METRICOOL_AUTOPUBLISH` = `false` if you want to approve every post on your phone at first; secret `NWS_USER_AGENT` = any text with a contact email, for weather alerts; photo keys `UNSPLASH_ACCESS_KEY`, `FLICKR_API_KEY`, `PIXABAY_API_KEY` |

Variables `METRICOOL_NETWORKS` (`facebook,instagram`) and `METRICOOL_AUTOPUBLISH` (`true`) already have the right defaults.
If the Metricool API tab is not on your plan, say so: the fallback is a scheduled Claude task that posts through the
Metricool connector instead (more of your Claude usage, no token).

## 2. What runs once that is in

1. Every 30 minutes (`7,37 * * * *` UTC) the workflow pulls the feeds, police, city and NWS sources, ranks what is new,
   writes the caption and the card, commits the image so Metricool can fetch it, then schedules the post for a few
   minutes later on Facebook + Instagram with the source, photo credit and the presumption-of-innocence line in the
   first comment.
2. One post per run, two in the 7-11am and 4pm waves, up to 20 a day, quiet from 11pm to 6am Central. Severe weather
   bypasses the quiet hours. Wanted bulletins are capped at one a day; the felony arrest log is off.
3. Photos: the official photo when the source is a government release (police, city, NWS); otherwise the verified
   Fort Worth photo library (`assets/photos`, filed by subject: Central Station for transit, the courthouse for a
   verdict, City Hall for council, the Capitol for a Texas bill, the skyline otherwise); search engines only for food,
   concerts and culture, and never a photo labelled with another city.
4. **Before anything publishes, two checks run.** After the caption is written, every sentence, number and quotation in it
   must be found in the source's own text (title, summary, article lead, the agency's fields); a Claude caption that fails
   is replaced by the template caption, which is built from the source's sentences, and a story that still fails is skipped.
   Right before publishing, the source link must still answer (a pulled article is never promoted) and a wanted bulletin's
   agency page is read again, so a fugitive caught since the run began is never posted. Held posts are listed in the run
   report with the reason.
5. If you also want a human tap on every post, set the variable `METRICOOL_AUTOPUBLISH` = `false`: each post then lands in
   the Metricool mobile app for approval instead of publishing itself.
6. After the first week, send the Page insights export (reach per post) and the mix gets tuned to what the audience answered.

## 3. What is covered ("everything Fort Worth and beyond")

- **News:** Fort Worth Report, Star-Telegram, FOX 4, NBC 5, WFAA, CBS Texas, Fort Worth Business Press, Fort Worth Magazine,
  Fort Worth Weekly, CultureMap, TCU, City of Fort Worth news, City of Arlington news, Fort Worth police releases.
- **Weather:** National Weather Service alerts, radar and the daily forecast for Tarrant County.
- **Events:** Ticketmaster for Dickies Arena, Billy Bob's, Texas Live and the Stockyards; the culture calendar
  (Stock Show, Juneteenth, Parade of Lights, Main Street Arts Festival, heat and freeze days).
- **Crime:** official wanted bulletins (FWPD, Arlington PD, DPS), never scraped jail records.
- **Texas and beyond, like the Dallas page:** up to eight posts a day from outside Tarrant County. Pro teams: Cowboys, Rangers,
  Mavericks, Stars, FC Dallas, Wings, Texans, Astros, Rockets, Spurs. Colleges: TCU and UT Arlington (local), the UT system
  (Austin, Dallas, UTSA, UTEP), Texas A&M, Texas Tech, Baylor, SMU, UNT, Texas State, Houston (ESPN league and college feeds,
  WFAA Sports, the Rangers' and Astros' own feeds). Worth-posting gate for all of it: two matching keywords, fresher than
  30 hours, not a trivia / podcast / gallery filler item, results and moves ranked above previews, one per story across
  outlets, no other-metro crime or traffic, and the daily share of eight. Statewide news: new Texas bills and the governor,
  H-E-B, Buc-ee's, Whataburger, gas prices, outages, ERCOT (The Texas Tribune, KERA, Texas Monthly, KXAN, KVUE, KHOU, KENS 5).
  Widen or narrow it in `config/sources.yaml` → `relevance.dfw_keywords` / `texas_keywords` and
  `config/brand.yaml` → `content_mix.non_local_per_day`.
- **Submissions:** the first comment asks for videos and photos. Pick an inbox (Google Form or Page messages) and approved
  submissions go into the queue with the "(via IG/ user)" credit.

## 4. Not yet, and why

- **X:** claim @fortworthdaily or @FortWorthDaily when you can; Metricool posts there too once connected.
- **TikTok / Reels:** the pipeline does not produce video yet. Fan clips from the inbox are the way in.
- **Website:** GitHub Pages site generated from the posts, after the socials are running.
