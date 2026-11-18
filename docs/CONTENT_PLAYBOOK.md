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

Scroll Dallas Texas TV and most media is not a photo they took. It is somebody else's post, shown inside theirs, with their
one-line caption above it: a DPD or Dallas Fire bulletin, a WFAA/FOX 4 headline, a venue's show announcement, a fan's
Instagram story from the stands. Two mechanics produce that look, and the pipeline does both:

| What they do | What we do | Where |
|---|---|---|
| Share another page's public Facebook post (Facebook nests it) | `extra.facebook_post_url` → Facebook publisher posts it as a share | `publishers/facebook.py`, mode `share` |
| Post a screenshot of a tweet / headline / bulletin as the photo | `card.style: quoted` renders the source's post as a card: name, domain or @handle, date, their text, their photo | `images/card.py: render_quote_card` |

Rules the quoted card follows so it is never a fake screenshot: it quotes the source's *own* public text (headline + first
sentence, or the bulletin fields), names the real source and where the text came from, shows no platform logo and no invented
engagement numbers, and keeps photo credits inside the card when the photo is not the source's. Booking photos are contained,
never cropped.

## 2. The Fort Worth copy: pillar → automated source → example post

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
