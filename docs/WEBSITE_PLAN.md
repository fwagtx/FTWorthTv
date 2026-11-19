# mytarrant.com: how the website should be set up

A plan, not a build. Nothing here is live yet. Decisions that only you can make are marked **DECIDE**.

## 1. What the site is for

The socials are the distribution; the website is the asset. Four things a Facebook page can never give you:

1. **An archive people can search.** Every post the pipeline publishes becomes a permanent page with the headline, our
   summary, the photo, the date and a link to the source. Facebook posts vanish from view in a day.
2. **Traffic that is not Meta's to give.** Google Search and Google Discover send readers to local news sites every day;
   a page with a few hundred well-structured articles starts to show up for "Keller ISD boundaries", "Utah TCU kickoff",
   "Fort Worth hail", and so on, with no algorithm change able to switch it off.
3. **An audience you own.** A newsletter list (and later push notifications) lives on the site. Meta can throttle reach;
   nobody can throttle an email list.
4. **A place to send people.** Stories already say "Full story on our page"; the first comment can say "More at
   mytarrant.com"; the page's About/Website field points there; and when the page is ready for ads, ads only make money
   on a site.

What it is **not**: a copy of other outlets' articles. The same rule as the captions applies: two or three sentences in our
own words, every sentence supported by the source, the source named and linked prominently. Our value is the roundup,
the weather, the events, the videos and the county-wide view, not somebody else's reporting.

## 2. Name and brand

The domain is MyTarrant, the page is Fort Worth Daily. **DECIDE** one of:

- **A (recommended): MyTarrant is the site and newsletter brand, Fort Worth Daily stays the flagship social brand.**
  The site masthead reads "MyTarrant" with "Fort Worth Daily and all of Tarrant County" under it; the socials link to
  the site, the site links to the socials. Later, city sub-pages (Arlington, Keller, Mansfield ...) can grow their own
  social pages under the same roof. This is how the domain name reads to a stranger: a county-wide local site.
- **B: rename everything MyTarrant** (page, handles, cards). Cleaner long-term, but it throws away the identity work and
  the handle @fortworthdailytv, and "Fort Worth Daily" is a stronger name for a daily news feed than "MyTarrant".

Either way the site uses the existing identity system: charcoal `#26282E`, off-white `#F7F7F5`, electric blue
`#2F5BFF`, Archivo for the masthead and Inter for text (both already in `assets/fonts/brand/`, open licences). A
"MyTarrant" wordmark in the same Overbar style is a one-hour job with the identity script.

## 3. The stack (all free)

| Piece | Choice | Why |
|---|---|---|
| Generator | Python + Jinja2 inside this repo (`python -m ftworthtv site build`) | One toolchain, tested like the rest; the pipeline already produces every field a page needs. No Hugo/Eleventy to learn. |
| Hosting | **GitHub Pages** from this repo, deployed by a workflow (`actions/deploy-pages`) | Free, HTTPS on a custom domain, no server, no CDN bill, and the content already lives here. Public repo = free Pages. |
| Domain | `mytarrant.com` at your registrar, pointed at GitHub Pages | Four A records + one CNAME; GitHub issues the certificate. Cloudflare (free) in front is optional later for caching and analytics. |
| Deploy trigger | `scripts/cycle.sh` runs `gh workflow run site.yml` after every real post; manual dispatch too | GitHub's cron proved unreliable; the watcher already knows when something was published. |
| Search on site | Pagefind (static index built at deploy) | No server, no JavaScript framework, works on a phone. |
| Analytics | Cloudflare Web Analytics or GA4 | Free; Search Console and Bing Webmaster Tools for indexing. |
| Forms (tips, videos) | A Google Form embedded on /submit, feeding the viewer-video sheet | Free; consent checkbox built into the form. |
| Newsletter (phase 3) | Buttondown (free to 100 subscribers) or Substack | A daily brief composed from the day's posts by the same pipeline. |
| Comments | None; each article links to its Facebook post for discussion | No moderation burden, no spam. |

Cost: the domain renewal only (yours already). Everything else is on free tiers with no card on file.

## 4. Content model

The publish step writes one record per published post, committed to the repo, so the site build is deterministic and
needs no network:

```
content/posts/2026/11/19/no-2-utah-visits-tcu.json
  headline, summary (the caption), category, scope, cities[], source {name, url}, published_at,
  image {path, credit, license, source_url}, facebook_url, instagram_url, video {youtube_id | mp4_url},
  kind (rss | nws_alert | event | wanted | video | submission), updated_at, corrections[]
```

Backfill: the posts already published (the hand-scheduled ones and everything in `state/posted.json`) get records from
their run folders, so the site opens with the full first week.

## 5. Pages

| URL | What is on it |
|---|---|
| `/` | Masthead, the latest 12 posts as cards (photo + headline + source + time), a weather strip (today's NWS forecast and any active alert), "This weekend", latest videos, city links. |
| `/news/<slug>/` | One post: headline, the card image, our summary, a large **Read the full story at <Source>** button, the Facebook post link, 3 related posts, "Report an error". JSON-LD `NewsArticle` with `isBasedOn` pointing at the source, Open Graph tags (the card is the share image). |
| `/<category>/` | news, weather, sports, events, things-to-do, safety, business, schools. |
| `/city/<name>/` | Fort Worth, Arlington, Keller, Southlake, Mansfield, Grapevine, North Richland Hills, Hurst, Euless, Bedford, Grand Prairie, Burleson, Crowley, Benbrook, White Settlement, Saginaw, Haslet, Azle: everything that names the city. |
| `/weather/` | Forecast, active alerts, the NWS radar loop (public domain), links to NWS Fort Worth. |
| `/events/` | This weekend and the next 14 days from the venue feeds already pulled (Dickies, Billy Bob's, Texas Live, the Stockyards). |
| `/video/` | YouTube link posts as official embeds (allowed by YouTube's terms; the channel keeps the view), viewer clips from the media release. |
| `/safety/` | Wanted bulletins while the agency lists them (the pipeline re-checks), with the presumption-of-innocence line. |
| `/submit/`, `/about/`, `/contact/`, `/corrections/`, `/privacy/` | The form, who we are, how to reach us, how we correct, what we collect (analytics only). |
| `/feed.xml`, `/sitemap.xml`, `/news-sitemap.xml`, `/robots.txt` | RSS for readers and aggregators, sitemaps for Google (the news sitemap is what Google News Publisher Center wants). |

Design: one column on phones, two on desktop, the card look from the posts (white, rounded photo), charcoal masthead.
No carousels, no pop-ups, no cookie banner needed (no cookies). Target Lighthouse 95+ on mobile; the site is plain HTML
and CSS with Pagefind as the only script.

## 6. Policies the build enforces

- **Attribution:** source name and link in the headline block and the button; summaries under 60 words; never the
  source's photo (our cards use library and licensed photos; the photo credit is printed on every page).
- **Crime on the web is different from crime on Facebook.** A post fades; a web page is found whenever someone searches a
  name, for years. **DECIDE** (recommended): wanted bulletins get pages with `noindex` and are removed the day the agency
  delists the person; arrest logs and mugshot posts are **not** published on the site at all. The social posts keep
  running as they do now.
- **Corrections:** a public `/corrections/` log; every article has a "Report an error" link; a corrected article shows an
  "Updated" line at the top with what changed.
- **Ads:** none until the site has traffic; when they come (AdSense, free to join), never on safety pages.
- **Privacy:** no accounts, no cookies, cookieless analytics, the Google Form is the only place a reader types anything.
- **Accessibility:** real headings, alt text (the headline), 16 px minimum text, contrast from the brand palette.

## 7. Rollout

**Phase 1, the site exists (about a day of work):** content records from the publish step and a backfill; the
generator with home, article, category, city and the static pages; RSS and sitemap; `site.yml` deploy; `CNAME`; a
"MyTarrant" wordmark. You enable Pages and add four DNS records (exact values in the setup doc when it is time).

**Phase 2, the sections:** weather, events, video and safety pages; Pagefind search; JSON-LD and Open Graph; Search
Console and Bing submission; the first comment on social posts gains "More at mytarrant.com".

**Phase 3, the audience:** the daily brief newsletter (composed by the pipeline, sent by Buttondown); Google News
Publisher Center and Discover eligibility (needs the news sitemap, author/about pages and a few weeks of history);
the tip and video form; AdSense when traffic justifies it.

## 8. What I need from you

1. **The domain.** Confirm mytarrant.com is registered to you and where its DNS is managed (the registrar name is
   enough). If it is not registered yet, registering it is the one thing in this plan that costs money.
2. **Brand decision** (section 2): A or B.
3. **Crime policy** (section 6): wanted bulletins noindex and auto-removed, arrest logs off the site.
4. **Two clicks on GitHub** when phase 1 is ready: Settings → Pages → Source: GitHub Actions, and the custom domain
   field. The automation cannot change repository settings itself.
