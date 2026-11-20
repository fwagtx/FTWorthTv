# Image rules: the picture must show what the post is about

The page's owner put it plainly: a photo that does not match the story makes the whole post look wrong. These are the
rules the pipeline enforces, the places real pictures legally come from, the mistakes already made (each one is a
regression row in `tests/fixtures/headline_subjects.json`), and the daily review that keeps the rules improving.

## 1. The rule

Read the headline for its named subject: a company (Anthropic), a team (Cowboys, TCU), a school district (Northwest
ISD), a person (Cooper Flagg), a venue (Dickies Arena), an institution (Fort Worth police). Then:

| The headline names | The photo must be | Never |
|---|---|---|
| a team or a school's sport | the team at its ground, or the ground itself | the campus chapel, a skyline |
| a company or a product launch | the company, its people, its product, its event | the exchange building, a generic office |
| a person | the person, or the team or institution they belong to | a stranger, a random crowd |
| a district, a police or fire department, a county court | the district's school, the department, the courthouse | downtown, the skyline |
| a place or landmark | that place | another city's landmark, ever |
| nothing in particular (a roundup, a statewide statistic) | the beat it is about (schools, grocery, storm, highway), then the city | a subject it does not mention |

If no verified photo of the subject exists, the card goes out with no photo. A blank card is honest; the wrong photo is a
lie about the story. (`images/subject.py` decides; `images/__init__.py` obeys; `checks.py` re-checks at publish time and
holds a post whose photo no longer fits.)

## 2. Where real, up-to-date pictures come from, in order

1. **The story's own image when the source owns it.** Police, city, county and NWS releases, Crime Stoppers bulletins,
   Ticketmaster event art: `image_policy: source_image`. The release's photo is the event.
2. **Official video, shared as a link.** A new upload on the agency's, team's, exchange's or wire's own YouTube channel
   becomes a Facebook link post that plays inline with the channel's own thumbnail (Nasdaq's feed of a bell ringing,
   the city's own video of a ribbon cutting). Nothing is downloaded or re-uploaded. `config/sources.yaml` → `youtube`.
3. **The verified photo library**, filed by hand under its subject (`assets/photos/library.json`): stadiums, arenas,
   stations, courthouses, schools, landmarks, companies. A football story takes `tcu-football`, not `tcu`.
4. **Open-licence search, newest first.** For a named subject the providers are asked for the newest Commons uploads
   whose file name carries the subject's words (`fresh:` queries), then any such file. A photo of last night's game beats
   a ten-year-old photo of the stadium. Openverse and Commons need no key; a free Flickr key (`FLICKR_API_KEY`) adds the
   largest pool of same-week Creative Commons photos of real events and is the single biggest upgrade available.
5. **Viewer photos and clips** from the submissions sheet, with consent and approval, credited to the sender.
6. **Claude looks at the picture** (`images/judge.py`), when `CLAUDE_CODE_OAUTH_TOKEN` is set: every provider photo for
   a named subject is downloaded and opened by headless Claude Code, which answers whether the image itself shows the
   headline's subject; a no drops it. **A person named in a headline is searched for only with this check in place.**
   Without the token, people stories use the venue, the team or the institution, or go out as a bare card, because a
   stranger who shares the name is the worst mistake a page can make.
7. **Recent pictures for things that happened.** A game, a concert, a ceremony, a parade, a storm, a crash: the search
   first insists on a picture taken within two weeks of the story (Commons records when a photo was taken), then falls
   back to the place. A years-old file photo is fine for a building; it is not a picture of Saturday's game.

Not allowed, however good the picture: AP, AFP, Reuters, Getty and station photos (licensed per use; the agencies
pursue reposts), screenshots of other pages' posts, another outlet's photo lifted from its article.

## 3. Lessons learned (each is a test)

| Date | What went out | Why it was wrong | Rule now |
|---|---|---|---|
| Nov 19 | Utah at TCU with a TCU campus building | the whole `tcu` topic was buildings | sports stories take the school's sports topic; `tcu-football` filled from Commons |
| Nov 19 | Northwest ISD boundaries with downtown Fort Worth | category default (community → downtown) | institutions take the beat that depicts them (school buses), never a street |
| Nov 19 | Anthropic IPO with the Nasdaq tower showing another company's ad | a venue stood in for the subject | a company is shown by the company; its venue is never a stand-in |
| Nov 19 | Anthropic IPO with a typographic numbers card | accurate but not a picture of the event | a real image of the event (Nasdaq's own feed, via the official video) comes first; a numbers card is a last resort |
| Nov 19 | Dallas City Hall story could have taken Fort Worth City Hall | the library's city-hall topic is Fort Worth's | another city's landmark is searched for, never swapped |
| Nov 20 | "Sunny, high near 65" forecast with a supercell | weather defaulted to the storm topic | weather pictures follow the conditions in the forecast (`weather_topics`) |
| Nov 20 | Two Dickies Arena events with a Fort Worth skyline | the provider search fell back to the city query after the subject found nothing | a named subject never gets the city fallback; the venue (library) comes first even for events |
| Nov 20 | "How two Democrats took ... Arlington House seats" with a skyline | "Democrats" was taken as the subject | parties and generic groups are not subjects; "House"/"Senate" map to the Capitol |
| Nov 20 | A country concert at Dickies Arena with a stranger's portrait, then with Ty Cobb at Fort Myers | the name was in the description, then its two words were scattered across a title | the whole name, in order, must be in the file name or title; descriptions never count; and a person is only ever searched for when Claude can look at the picture |
| Nov 20 | A basketball showcase and a country concert at Dickies Arena with a K-pop concert photo | the file was titled "Twice - Dickies Arena" and the venue words matched | a venue is searched as a building (its category, "exterior", "building"); a photo of somebody else's show is never used for an event; the lesson row is in the fixture |

## 4. The daily review

Every published post is written to `state/review/<day>.jsonl` with its headline, the photo's subject label (`entity:…`,
`topic:…`, `beat:…`, `own`), the credit and the card path. The morning check-in reads yesterday's file and the committed
cards, looks at each picture next to its headline, and turns every mismatch into a rule change and a new row in the
lessons file the same day. The checklist for each post:

1. Does the picture show the headline's named subject, or the beat when there is none?
2. Is it current? A years-old file of a building is acceptable for a building; a game, a ceremony, a storm or an opening
   wants a picture from the event itself or none.
3. Is the credit right and the licence one of ours (public domain, CC BY, CC BY-SA, CC0, the source's own release)?
4. Would a reader who knows the subject see the connection in one second?
