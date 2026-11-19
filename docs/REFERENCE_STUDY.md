# Studying the reference page (Dallas Texas TV) with Claude for Chrome

I cannot open Facebook from the build environment, so the study runs in your browser. Paste the prompt below into Claude for
Chrome on a tab where you are logged into Facebook, let it work, save the JSON it produces, and hand the file back to me (or
drop it in the repo as `study/dallas-texas-tv.json`). Then:

```
python scripts/ingest_reference_posts.py study/dallas-texas-tv.json
```

That writes `config/reference_profile.json` (their cadence by hour, media mix, category mix, caption length, how often the
media is a screenshot of their own post) and `config/caption_examples.json` (their 40 best-performing captions). The Claude
writer reads the examples on every caption, and the script prints suggested `caps_per_day` for `config/brand.yaml`.

## The prompt

```
You are helping me study a public Facebook page so I can build a similar page for another city. Go to
https://www.facebook.com/DallasTexasTV and work through the page carefully. I need structured data, not a summary.

1. Page basics: page name, follower count, the Intro/About text, category, any links, pinned posts, whether the page
   is verified, and the names of their story highlights if visible.

2. Posts: scroll the feed and collect the most recent 120 posts (keep scrolling until you have them; expand "See more"
   on each caption so you capture the full text). For every post record:
   - posted_at: date and time as shown (convert "5 days ago" style stamps to an ISO date-time in Central time, best effort)
   - caption: the full caption text exactly as written, line breaks preserved as \n
   - media_type: one of photo, video, reel, album, link, share, text
   - media_description: one sentence on what the media shows. If the image is a screenshot of one of their own X/Twitter
     posts (their logo, "Dallas Texas TV @DallasTexasTV", a headline line, then a photo), write "x_screenshot: " followed
     by the exact headline text on the card.
   - headline_on_card: the headline text printed on the screenshot card, if any
   - source_credit: any "via", "credit", "📸", "🎥", or outlet name in the caption or first comment
   - first_comment: the text of the page's own first comment if there is one
   - reactions, comments, shares: the counts shown (numbers; 17.1K -> 17100)
   - views: for videos/reels if shown
   - hashtags: list; location_tag: the "is in <place>" text; sponsor_line: any "official partner of ..." text

3. Also note, in a "notes" field: how many posts per day they seem to make, the hours they post most, which post types get
   the most reactions, how often captions are one sentence versus two short paragraphs, and anything recurring
   (series names, weather posts, wanted posts, fan-submitted videos).

Output ONLY a JSON object with this shape and nothing else:
{"page": {"name": "", "url": "", "followers": 0, "about": "", "category": "", "verified": true, "links": [], "pinned": [], "highlights": []},
 "posts": [{"id_or_url": "", "posted_at": "", "caption": "", "media_type": "", "media_description": "", "headline_on_card": "",
            "source_credit": "", "first_comment": "", "reactions": 0, "comments": 0, "shares": 0, "views": null,
            "hashtags": [], "location_tag": "", "sponsor_line": ""}],
 "notes": ""}
Do not invent values: use null when something is not shown. Do not include any personal data about commenters.
```

If Claude for Chrome stops early, ask it to "continue from post N and append to the same JSON". Two runs on different days
(one weekday, one weekend) give a better cadence picture than one.

## What I do with it

| From the study | Into the pipeline |
|---|---|
| category mix | `content_mix.caps_per_day` in `config/brand.yaml` |
| hour-of-day histogram | `posting.quiet_hours_local` and the cron in `.github/workflows/post.yml` |
| share of screenshot cards vs. photos vs. video | `card.style` default and how often a plain photo is used instead of the card |
| caption length and the one-line vs. two-paragraph split | the writer's rules (`DALLAS_CAPTION_RULES`) and `caption.max_chars` |
| the 40 best captions | `config/caption_examples.json`, shown to the Claude writer as voice examples |
| recurring series | entries in `config/culture.yaml` (weather, wanted, "this weekend", heat/freeze memes) |
