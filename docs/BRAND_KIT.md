# Fort Worth Daily — brand kit

Identity direction **B, "The Overbar"**, chosen from the three directions in `assets/brand/identity/` (boards `board-A/B/C.jpg`).
Everything below is generated: `python scripts/make_identity.py` (marks, wordmarks, lockups, boards),
`python scripts/make_identity_uploads.py` (profile pictures and Facebook covers for upload),
`python scripts/make_brandkit_identity.py --direction B` (the platform kit in `assets/brand/kit-B/`).
The pipeline reads only `assets/logo.png` (the post-card avatar), which the kit script writes.

## 1. Identity

| | |
|---|---|
| Name | **Fort Worth Daily** |
| Short form | FWD (the monogram); "FWD" also reads "forward" |
| Handle | **@FortWorthDaily** (14 characters, fits X's 15-character limit). Fallback: @FWDaily |
| Tagline | Fort Worth, every day. |
| Category | Media/News Company (Facebook) · Media (Instagram, X, TikTok) |
| Location | Fort Worth, TX |
| Voice | Plain, fast, local. Facts first, no hype words, no corporate "we". |
| Avoid | "FWTV" / "Fort Worth TV" (the city's own channel), navy-and-gold Texas clichés, stars, longhorns, skylines |

## 2. The mark

**The Overbar.** F, W and D hang from one shared bar: it is the F's top arm, the shoulder line the W drops from, and the
top of the D, all at once. One silhouette, nothing else in the market has it. Drawn as geometry (`scripts/make_identity.py`,
`mono_b`), not typed. Uniform stroke, flat terminals on the W, the D's bowl a true semicircle.

| File (`assets/brand/identity/`) | Use |
|---|---|
| `B-mono-1600.png` / `B-mono.svg` | primary monogram, charcoal, on light backgrounds |
| `B-mono-bw-1600.png` | one colour black |
| `B-wordmark-1600.png` | FORT WORTH wide + DAILY condensed in electric blue |
| `B-lockup-1600.png` | monogram + wordmark, horizontal |
| `B-profile-1600.png` | off-white monogram on a charcoal disc (the profile mark) |
| `upload/B-profile-1024.png` | **profile picture for Facebook and Instagram** (square, circle-safe) |
| `upload/B-cover-1640x624.png` | **Facebook cover**, off-white; `kit-B/cover-facebook-1640x624.png` is the charcoal version |
| `fort-worth-daily-logos.zip` | everything above plus the A and C directions, with vector sources |

Rules: clear space of one bar-thickness around the monogram; never below 32 px (use the profile disc there); never
re-draw the letters in a typeface; the blue is only ever the word DAILY, a rule, or a ring, never the monogram.

## 3. Colour

| Token | Hex | Use |
|---|---|---|
| Charcoal | `#26282E` | the mark, dark backgrounds, body text on light |
| Off-white | `#F7F7F5` | light backgrounds, the mark on dark |
| Electric blue | `#2F5BFF` | DAILY in the wordmark, highlight rings, one accent per layout |
| Muted | `#B9BCC6` | secondary text on charcoal |

The post card stays white with near-black text, as the reference format requires; the brand colours live on the profile,
covers, stories and highlights.

## 4. Type

- **Wordmark:** Archivo (variable), FORT WORTH at width 125 / weight 600 with 10 % tracking, DAILY at width 62 / weight 900.
  The contrast is width, not weight: wide and light against condensed and black, one baseline.
- **Kit and UI text:** Archivo for labels and covers; Inter for the post card and captions.
- All faces are SIL Open Font License, files and licences in `assets/fonts/brand/`.

## 5. Platform files (`assets/brand/kit-B/`)

| Platform | File | Size |
|---|---|---|
| Facebook page | `identity/upload/B-profile-1024.png` + `cover-facebook-1640x624.png` (charcoal) or `identity/upload/B-cover-1640x624.png` (off-white) | 1024² / 1640×624, text inside the 1100 px centre |
| Instagram | `avatar-1024.png`, highlights `highlight-*.png` | 1024² / 1080² |
| X | `cover-x-1500x500.png` | 1500×500 |
| YouTube | `cover-youtube-2560x1440.png` | content inside the 1546×423 safe box |
| LinkedIn | `cover-linkedin-1584x396.png` | 1584×396 |
| Stories / reels | `story-template-1080x1920.png`, `watermark-handle.png` | 1080×1920 / pill |
| Post card | `assets/logo.png` (written by the kit script) | avatar on every post |

## 6. Bios (paste as-is)

- **Facebook intro (101 chars):** `Independent news, culture and entertainment for Fort Worth. Every day. DM us your videos 📲`
- **Instagram (150):** `Fort Worth, every day.` / `Independent news · culture · entertainment` / `DM us your videos & photos 📲`
- **X (160):** `Independent news, culture and entertainment for Fort Worth, Tarrant County and Arlington. Every day. DM us your videos 📲`
- **TikTok (80):** `Fort Worth, every day. DM us your videos 📲`
- **YouTube / About:** `Fort Worth Daily is an independent news, culture and entertainment page for Fort Worth, Tarrant County and Arlington: what happened today, what is on this weekend, where to eat, the weather, the Cowboys and TCU, and the people who make the city. Every source and every photo is credited. Not affiliated with any TV station or with the City of Fort Worth.`

## 7. The post, in one paragraph

Caption: a plain 2–4 sentence summary of the story in two short paragraphs, no hashtags, no link, no follow line, at most
one emoji (🚨 for incidents). Media: our white card with the FWD avatar, "Fort Worth Daily", "@FortWorthDaily", a one-line
news headline and the photo. First comment: `Source: <outlet> <url>`, the photo credit, `DM us your videos & photos 📲`, and
the presumption-of-innocence line on any wanted/arrest post. `docs/CONTENT_PLAYBOOK.md` has the content mix and rhythm.

## 8. Which socials, and why

| Priority | Network | Role | How it is fed |
|---|---|---|---|
| 1 | **Facebook Page** | the audience; where the reference format performs | automated from day one (Metricool) |
| 1 | **Instagram** (+ Threads) | same posts, plus stories from the template | automated from day one (Metricool) |
| 2 | **X** | the wire: police, stations and reporters post there first; claim the handle | automated via Metricool; small reach for a year |
| 3 | **TikTok** | video only; claim the handle, post manually with clips | manual |
| 4 | YouTube Shorts | later, with video | manual |
| – | LinkedIn, Pinterest, Snapchat | not for this page | – |

Cadence once live: Facebook six to ten posts a day, X mirrors all of them, Instagram two or three feed posts plus stories.

## 9. Creating the socials — checklist

1. **Facebook Page**: name `Fort Worth Daily`, category *Media/News Company*, bio from §6, profile `upload/B-profile-1024.png`,
   cover `kit-B/cover-facebook-1640x624.png`, username `FortWorthDaily`, location Fort Worth, TX. Turn on messaging.
2. **Instagram** (Business account): username `FortWorthDaily`, bio from §6, same profile picture, link the Page. Upload the six
   highlight covers as the first story of each highlight (News, Events, Food, Weather, Sports, Wanted).
3. **X**: handle `FortWorthDaily`, header `kit-B/cover-x-1500x500.png`, bio from §6.
4. **TikTok**: username `fortworthdaily`, bio from §6, same profile picture.
5. **YouTube** (optional now): channel `Fort Worth Daily`, banner `kit-B/cover-youtube-2560x1440.png`.
6. Take the same handle everywhere the same day. Then follow `docs/GO_LIVE.md` to connect Metricool and the secrets.

## 10. Legal lines to keep

- Wanted / arrest posts always carry: *Charges are accusations. All suspects are presumed innocent until proven guilty in a court of law.*
- Stock and Creative-Commons photos are credited in the first comment (`card.photo_credit_on_card: true` moves it onto the card).
- Official photos (police releases, city, NWS, Ticketmaster event art) are used as the agency publishes them.
- "Daily" is a promise the scheduler keeps; say "page" rather than "newspaper" in the About text.
