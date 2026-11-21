# Go live: where things stand and what is still needed

Page: **Fort Worth Daily** on Facebook, **@fortworthdailytv** on Instagram, both connected to the Metricool brand
(brand id 8208939, timezone America/Chicago). The first posts were scheduled through Metricool on Nov 18-19, 2026.
Nothing here costs money: free tiers plus the Claude subscription and the Metricool plan you already have.

## 1. How publishing works now: no secrets, a person looks at every card

Nothing has to be added on GitHub or in Metricool. The owner asked (Nov 20) that every post be checked before it goes
out and that nothing be left for them to set up, so the page publishes like this:

1. **GitHub generates.** `render.yml` runs the pipeline against the live sources (feeds, police, city, NWS, YouTube
   channels, the viewer sheet) as a dry run and pushes the run folder, cards and stories included, to a `renders/<run>-<n>`
   branch. The cards are public there (raw.githubusercontent.com), which is what the scheduler needs.
2. **A scheduled Claude session publishes** ("Fort Worth Daily · publish", every half hour, 6 am to 10:30 pm Central).
   It dispatches a render, waits for the branch, runs `ftworthtv session queue <run folder> --branch <branch>`, which
   writes a manifest with each draft's headline, caption, first comment, image URLs, pre-publish problems and the exact
   Metricool payloads. The session **opens every card** and checks the picture against the headline (docs/IMAGE_RULES.md),
   drops or fixes what does not fit, schedules the rest through the Metricool connector (post, then its Story two minutes
   later), and records them with `ftworthtv session record`, which updates `state/posted.json` and the review log and is
   pushed so the next render skips them.
   The record step runs every cycle, posts or not: it also remembers drafts that only a daily category cap held back,
   so the next day's render may still take them while they are under 36 hours old.
   `posting.networks` in `config/brand.yaml` follows the brand's connections in Metricool: every cycle reads them
   (getBrandSettings) and drops or restores Instagram on its own, so a disconnected network never blocks Facebook.
3. **Viewer photos and clips** come in the same way: the session reads the sheet "Fort Worth Daily — viewer videos" and
   the uploads folder through the Drive connector (no public sharing needed), checks consent and approval, hosts a clip
   on the media release and posts it credited.

The REST path (`METRICOOL_USER_TOKEN` and friends in `watch.yml`) still works if those secrets are ever added; it is
no longer required. The hourly limit of scheduled tasks is the only reason the cadence is half-hourly rather than the
watcher's seven minutes; severe weather alerts are the one thing that path handled faster.

## 2. What runs once that is in

1. A watcher (`.github/workflows/watch.yml`) polls the feeds, police, city and NWS sources every seven minutes inside one
   long run and starts the next run before it ends, so it never depends on GitHub's cron (which dropped most scheduled runs
   here). If the chain ever breaks, a half-hourly cron restarts it, and so can you: Actions → "Watch and post" → Run workflow.
   Each cycle ranks what is new,
   writes the caption and the card, commits the image so Metricool can fetch it, then schedules the post for a few
   minutes later on Facebook + Instagram with the source, photo credit and the presumption-of-innocence line in the
   first comment.
2. One post per run, two in the 7-11am and 4pm waves, at least 25 minutes apart, up to 20 a day, quiet from 11pm to 6am
   Central. Severe weather and breaking news bypass the spacing and the quiet hours, so they go out on the next run, which
   is at most ten minutes away. Wanted bulletins are capped at one a day; the felony arrest log is off.
3. Photos: the official photo when the source is a government release (police, city, NWS); otherwise the verified
   Fort Worth photo library (`assets/photos`, filed by subject: Central Station for transit, the courthouse for a
   verdict, City Hall for council, the Capitol for a Texas bill, the skyline otherwise); search engines only for food,
   concerts and culture, and never a photo labelled with another city.
4. **Every post also goes out as a Story** on Facebook and Instagram two minutes after the feed post: the same card on the
   brand's charcoal, 1080x1920, with the page name on top and "Full story on our page" at the bottom (`config/brand.yaml`
   → `stories`).
5. **Before anything publishes, two checks run.** After the caption is written, every sentence, number and quotation in it
   must be found in the source's own text (title, summary, article lead, the agency's fields); a Claude caption that fails
   is replaced by the template caption, which is built from the source's sentences, and a story that still fails is skipped.
   Right before publishing, the source link must still answer (a pulled article is never promoted) and a wanted bulletin's
   agency page is read again, so a fugitive caught since the run began is never posted. Held posts are listed in the run
   report with the reason.
6. If you also want a human tap on every post, set the variable `METRICOOL_AUTOPUBLISH` = `false`: each post then lands in
   the Metricool mobile app for approval instead of publishing itself.
7. After the first week, send the Page insights export (reach per post) and the mix gets tuned to what the audience answered.

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
- **National moments, like the Dallas page:** at most two a day from Variety, The Hollywood Reporter, Billboard, IGN, The Verge,
  Deadline, NPR and ESPN's top headlines. A story gets in only two ways: it hits the watchlist (GTA VI, the Super Bowl, the World
  Series, the Oscars, a Powerball jackpot, Spotify Wrapped, Black Friday, daylight saving ...) or it carries a big-moment term
  (release date, box office, series finale, tour dates, dies at, Netflix, iPhone, SpaceX ...) that at least two of those outlets
  are running at the same time. Crime and traffic from elsewhere never qualify, and a moment is posted once, not once per outlet.
  Edit `config/sources.yaml` → `relevance.watchlist` / `national_keywords` and `config/brand.yaml` → `content_mix.national_per_day`.
- **Video from other channels (shared, never copied):** 21 public YouTube channels are watched: City of Fort Worth, Tarrant
  County, Trinity Metro, Fort Worth police, City of Arlington, NWS Fort Worth, Fort Worth Report, Visit Fort Worth, the
  Stockyards, the Zoo, TxDOT, FOX 4, NBC 5, WFAA, CBS Texas, KERA, Cowboys, Rangers, Mavericks, Stars, FC Dallas. A new
  upload becomes a Facebook post carrying the YouTube link (it plays in the feed, credited to the channel, link in the first
  comment); the file is never downloaded or re-uploaded, so the channel keeps its views and there is nothing for Rights
  Manager to flag. The gate is strict: newer than 12 hours; no live streams, full games, meetings, podcasts or filler; a
  station's video only when its own title names Fort Worth, a Tarrant-side city or the region (DFW, North Texas), so a crash
  into a Dallas home or a Dallas ISD vote does not qualify; a team's video only for results, highlights, press conferences
  and roster moves. Three a day, one per cycle, Facebook only (Instagram does not take links). Tune `config/sources.yaml` → `youtube`.
- **Viewer video (posted natively, credited):** the first comment asks for clips. When one arrives by DM you check the two
  things no program can, that the sender shot it and agrees to it being posted with credit, then save the file in the Drive
  folder **Fort Worth Daily — viewer video uploads** and add a row to the sheet **Fort Worth Daily — viewer videos** (credit,
  caption, where, the file's Drive link, consent = yes, approved = yes). The next cycle downloads the clip, hosts it on a
  GitHub release (`media-YYYY-MM`) and posts it as a Facebook video with the credit in the caption and the first comment;
  two a day at most, each row posted once. Instagram gets it as a Reel only when `config/brand.yaml` → `video.instagram` is
  on and the clip is portrait (off until you have checked the first one). **One step left for you:** in Google Drive, share
  the uploads folder as *Anyone with the link → Viewer* (the sheet and the clips inside inherit it); the automation was not
  allowed to grant that itself. Until then the sheet reads as a sign-in page and the source only logs a warning.
- **Radar video:** on a severe alert the NWS Fort Worth radar loop (public domain) becomes a short MP4 and goes out as a
  video post instead of the card; if the video is refused, the card goes out. `config/brand.yaml` → `posting.weather_radar_video`.

## 4. Not yet, and why

- **X:** claim @fortworthdaily or @FortWorthDaily when you can; Metricool posts there too once connected.
- **TikTok:** not connected. **Reels:** native clips can go to Instagram as Reels (`config/brand.yaml` → `video.instagram`),
  kept off until the first one has been checked by hand. Station and creator video is never re-uploaded as a Reel.
- **Website:** GitHub Pages site generated from the posts, after the socials are running.
