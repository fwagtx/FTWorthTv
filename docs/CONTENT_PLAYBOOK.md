# Content playbook: what Dallas Texas TV posts, and the Fort Worth copy of it

Built from every Dallas Texas TV post that is indexed outside Facebook (their X account, TikTok, Facebook video pages, and
press that credited them), plus D Magazine's 2021 profile of the account. Facebook itself cannot be read by a bot, so this is
a sample of ~40 posts across 2021–Nov 2026, not the full feed. It is consistent enough to copy.

## 1. Their content, ranked by how much of the feed it is and how hard it hits

| # | Pillar | Share | Real examples (their captions) | Typical reach |
|---|--------|-------|-------------------------------|---------------|
| 1 | **Caught on camera, right now** — chases, wrecks, fights, road rage, tasings, fires, people running | ~30% | "Video of footage of a vehicle flying off the High Five in Dallas today" · "Things got heated between Cowboys and 49ers fans at Texas Live during the game. Arlington police responded to the scene. 🚨" · "Wild police chase ending near 75 and Walnut Hill in Dallas" · "Road rage caught on video at a Dallas intersection today" | the viral tier: 300K–4M views |
| 2 | **Concerts & celebrity moments** — who played, who showed up, fans lining up | ~15% | "Kid Cudi joins Kanye at AT&T" · "Beyoncé arrives at AT&T Stadium ahead of her show tonight (via IG/ gameinsidegame)" · "Fans waiting in the rain outside of American Airlines Center ahead of Drake concert tonight (via @…)" · "XTC in Dallas last night, Full video on our Instagram" | 10K–100K |
| 3 | **Fan culture & big-event energy** — World Cup fans, Cowboys game days, State Fair, snow days, heat | ~10% | "Netherlands fans have taken over Dallas" · "DALLASKA IS OFFICIALLY BACK" · "Everyone in Texas right now" · State Fair fire clip · fight on the Midway on the fair's last night | 100K–1.3M |
| 4 | **One-liner local news** — rankings, openings, big decisions, consumer alerts, PSAs | ~20% | "Dallas was ranked the top U.S. Thanksgiving destination for 2026" · "Nine new stores are coming to Dallas' Henderson Ave, including Lululemon, Vuori and Frankies Bikinis" · "Plano voters oppose arena tax for new Dallas Stars venue at Willow Bend" · bank outages at Chase/Wells Fargo/BofA · free sandbags in Fort Worth & Haslet before heavy rain (with addresses + phone) | 10K–50K |
| 5 | **Weather & traffic drama** | ~10% | "635 Today" · "I-635 in Mesquite this morning as heavy rain moves through DFW" · "the lightning in DFW tonight" · "Currently raining money in downtown Dallas" | 5K–50K |
| 6 | **Funny / relatable** | ~5% | "Downtown Dallas, how does this happen 😂" · "SOUND UP" (1.1M likes) · Halloween house "🎃🎃🎃" · "Happy Halloween Dallas" | spikes |
| 7 | **Statewide wallet politics** (not local council) | ~5% | Texas bill to eliminate property taxes · bill to make English the official language | 10K–50K |
| 8 | **Crime from police** | ~5% | "Dallas police chase ends with a crash and shooting on southbound I-35 in Red Oak" · tasing in Deep Ellum | 50K–300K |

What they do **not** post: long captions, hashtags on Facebook/X (only on TikTok: #Fyp #Dallas #DFW #News), headline graphics,
link previews, bullet lists, city-council process stories, obituaries, press-release language.

**Format rules they never break**
- One sentence, present tense, no trailing period; two sentences only when there is a second fact ("… during the game.
  Arlington police responded to the scene. 🚨").
- Media is the phone video or the photo itself. Their own `@DallasTexasTV` watermark on videos. Location tag on the post.
- Credit the person who filmed it inline, always the same shape: "Views from the sky tonight across DFW (via IG/ its_me_gabriela_)",
  "Large fire on Dallas North Tollway and Spring Valley this afternoon (via IG/ brentlindeman)", "Beyoncé arrives at AT&T Stadium
  ahead of her show tonight (via IG/ gameinsidegame)". The formula is `<what> <where> <when> (via IG/ user)`.
- Instagram cross-promo: "Full video on our Instagram @DallasTexasTV" / "Follow us on Instagram @DallasTexasTV".
- Emoji: at most one, 🚨 for incidents, 😂 for funny; most posts have none.
- Cadence: roughly 6–10 posts a day on X (19.6K posts since Feb 2020); Facebook gets the strongest 3–6.
- Sub-brands for volume: @dallastexastvsports, @dallasmicdup (street interviews, 232K), DTX TV Media. Instagram is their biggest
  surface (@dallastexas_tv ≈ 1.6M followers vs 647K on Facebook), which is why every post pushes Instagram. One sponsor
  (a law firm) is credited as "official partner" across all accounts.

## 1b. The format that carries most of their feed: a post inside a post

Two real posts from the page (Nov 2026), measured from screenshots:

**Caption** (above the media, two short paragraphs, plain facts, a quote when the article has one, nothing else):

> Rep. Eddie Morales Jr. of Eagle Pass filed House Bill 410. It would make it illegal for ICE agents in Texas to cover their faces.
>
> Supporters say agents should be identifiable. ICE says masks protect agents from being targeted.

> Texas Lt. Gov.-elect Vikki Goodwin says a bill to regulate THC will be one of her top priorities when lawmakers meet in January. "I'm not interested in a full ban on THC," she said.
>
> Incoming Agriculture Commissioner Clayton Tucker went further. He called hemp a possible "saving grace" for Texas farmers.

**Media**: a screenshot-style card of *their own* post. White, edge to edge. Top left their round logo (about 7% of the
width), "Dallas Texas TV" in bold with the blue check, "@DallasTexasTV" in grey under it. Then one headline line in plain
(not bold) type, about 3% of the width tall, wrapping to two lines: "New Texas bill filed would ban ICE agents from wearing
masks/face coverings", "New Texas leaders say THC rules are a top priority for 2027". Then the photo with rounded corners,
3:2, inset about 13.5% on each side. No date, no like counts, no platform logo. The whole image is about 1.3:1.

What the pipeline does with it: `card.style: tweet` renders exactly that card for every post (`images/card.py:
render_tweet_card`) with our logo, "Fort Worth Daily", "@FortWorthDaily", the writer's `headline` and the photo; the
caption writer follows the two-paragraph rule above (`writer.py: DALLAS_CAPTION_RULES` for Claude, `dallas_caption` for the
template). The blue check is off until the page is verified (`card.verified_badge`).

## 1c. What the study of 120 of their posts showed (Nov 13–18, 2026) and what changed because of it

| Finding (from `study/dallas-texas-tv.json`, ingested by `scripts/ingest_reference_posts.py`) | What the pipeline now does |
|---|---|
| 20–24 posts a day, from about 5:45am to 10:30pm; busiest 7–11am with a second wave at 4pm | runs every 10 minutes, 1 post per run and 2 during the 7–11am and 4pm hours, 25 minutes apart, cap 20 a day, quiet 11pm–6am |
| every one of the 120 posts is the same screenshot card: their logo, name and handle, a one-line headline, a photo | `card.style: tweet` for every post (unchanged) |
| the caption never repeats the headline; 1–3 short paragraphs, median 257 characters, 90th percentile 397 | the writer's rules and examples (`config/caption_examples.json`, their 40 best captions) |
| no hashtags, no emoji in captions, no "via" lines; sources credited inline ("according to ESPN") | `caption.emoji: false` strips any emoji; submission credits moved to the first comment |
| topic mix: sports 24 %, outages/gaming/rankings/prices 19 %, weather 15 %, Texas bills and politics 12 %, business 8 %, events 8 %, crime 7 % | `caps_per_day` re-set to that mix; politics allowed (state and local only) |
| the best-performing topic is "New Texas bill filed would…" (3–4× the reactions of sports); H-E-B, gas prices and school posts also lead | DFW-wide and Texas-wide stories are now kept at a lower weight, one per run, with The Texas Tribune and KERA added as sources |
| live game coverage: preview, touchdowns, halftime, final, next-day quotes, every 15–45 minutes | not built yet; needs a live-score source (ESPN's public scoreboard) and is the next feature |
| video is pushed to the comments ("Video in comments") or linked as an Instagram reel in their own first comment | the first comment already carries links; clips from the inbox will go there |

## 2. The Fort Worth copy: pillar → automated source → example post## 2. The Fort Worth copy: pillar → automated source → example post

| Pillar | Fort Worth source (in this repo) | Example output |
|--------|----------------------------------|----------------|
| Caught on camera | **needs people**: a submissions inbox (DM/email/Google Form) → human one-tap approve. Automated stand-ins today: traffic stories matched to TxDOT cameras, NWS radar, police releases, Reddit r/FortWorth (off by default) | "I-35W at 28th this morning 🚨" with the live camera frame |
| Concerts & celebs | Ticketmaster (Dickies Arena, Billy Bob's, Bass Hall, Texas Live), CultureMap/Star-Telegram "last night" coverage, Ticketmaster artist images | "Ty Myers at Dickies Arena this Saturday. Tickets in the comments 🎟️" |
| Fan culture & big events | `config/culture.yaml` calendar (Stock Show, Juneteenth/Opal Lee, State Fair, Halloween, Parade of Lights, World Cup at AT&T Stadium), TCU/Cowboys/Rangers keywords, heat/freeze memes from the NWS forecast | "Everyone in Fort Worth right now 🥵" · "Parade of Lights rolls through downtown Fort Worth this Sunday 🎄" |
| One-liner local news | 13 feeds + City of Fort Worth + Arlington listings, with buzz-word boosts (ranked, coming to, opening, closing, free, outage, recall) | "New H-E-B store north of Fort Worth to open in time for 2026 holidays" · "Tarrant County bans tax abatements for data centers" |
| Weather & traffic | NWS alerts (radar image), daily forecast, traffic feeds, cameras | "Severe Thunderstorm Warning issued for Tarrant County until 7:30 PM 🚨" · "Sunny and a high of 65 in Fort Worth today" |
| Funny / relatable | template memes on extreme weather; everything else needs the inbox | "Freezing tonight in Fort Worth, low of 28 🥶" |
| Statewide wallet politics | off by default (`exclude_categories: [politics]`); turn on and cap at 1/day if wanted | — |
| Crime from police | FWPD/Arlington/DPS WANTED bulletins with the agency photo, police releases, optional felony arrest log | "Fort Worth police are looking for …, wanted for aggravated robbery. Crime Stoppers is offering up to $2,000 for information leading to an arrest 🚨" |

Daily caps that keep the balance Dallas has (`content_mix.caps_per_day` in `config/brand.yaml`): traffic 3, weather 3,
events 3, culture 3, sports 3, community 3, business 2, food 2, crime 2, other 1, politics 0. Severe weather ignores caps.
A story that only a cap kept out (the fourth community item of a busy day) is remembered by the session's `record` step
and may still run the next day while it is under 36 hours old; the ordinary freshness window holds for everything else.
The writer looks at up to a dozen ranked candidates a run, so a few that a cap or the date gate hold back do not starve it.
A video description is cut before the channel's boilerplate before anything reads it, and a headline with a crime word
(convicted, arrested, wanted, fraud) is crime whatever the body says, so the crime cap counts it.

## 3. A day on the page (what the scheduler produces when the sources are busy)

| Central time | Post | Pillar |
|---|---|---|
| 7:00 | "Sunny and a high of 65 in Fort Worth today" (or the heat/freeze meme) | weather |
| 9:00 | best one-liner news of the morning (ranking / opening / decision) | news |
| 11:00 | culture-calendar post if a window is open, else events "this weekend" | culture / events |
| 13:00 | traffic/incident or police item, or WANTED (max 1/day by default) | right now / crime |
| 15:00 | food or business one-liner | news |
| 17:00 | sports/fan-culture or concert "tonight at Dickies" | events |
| 19:00 | second news one-liner or community story | news |
| 21:00 | "last night" / recap when the feeds have it | concerts |

Severe weather alerts post immediately whenever they fire, quiet hours 11pm–6am.

## 4. What still needs a human to reach Dallas-level reach

1. **The viral tier (pillar 1) is crowd-sourced.** Build the inbox: "DM us your videos & photos 📲" is already in every first
   comment. A Google Form or a Page-inbox webhook plus a one-tap approve step would feed `ftworthtv run --stories` directly.
   A submitted story carries `"extra": {"credit": "IG/ username"}` and the caption comes out exactly in the Dallas shape:
   `Large fire on I-35W and Western Center this afternoon (via IG/ username)`.
2. **Celebrity sightings** come from the same inbox.
3. **"Full video on our Instagram"** needs Instagram publishing (Metricool path works today).
4. **Street interviews / mic'd up** sub-brand is a separate production.

Everything else in the table above runs itself.
