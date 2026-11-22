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
| something that happened (a play, an injury, a crash, a fire, a ceremony, an arrest) | a picture of that happening, or the outlet's own photo in a link preview | the stadium, the highway, the building: a stand-in is a lie about the event |

If no verified photo of the subject exists, the story is not posted. The owner saw Facebook's link preview, the
fallback used on Nov 20, as "a post inside a post": the page posts original cards only, so a story we cannot illustrate
honestly waits for a picture or is skipped (`posting.link_when_no_photo: false`). The wrong photo is a lie about the
story; a link preview is somebody else's post. (`images/subject.py` decides; `images/__init__.py` obeys; `checks.py` re-checks at publish time and
holds a post whose photo no longer fits.)

## 2. Where real, up-to-date pictures come from, in order

1. **The story's own image when the source owns it or lets us use it.** Police, city, county and NWS releases, Crime
   Stoppers bulletins, Ticketmaster event art, and the two newsrooms whose terms allow a noncommercial page to republish
   their stories with their photos: the Fort Worth Report (CC BY-ND 4.0, credit, no edits, tag @FortWorthReport) and The
   Texas Tribune (photos with the stories they ran with, credit "Name, The Texas Tribune"). `image_policy: source_image`,
   the photographer's credit read from the page's caption, the photo shown whole and never cropped. The stations' photos
   (NBC 5, FOX 4, WFAA, CBS, the Star-Telegram) are not licensed for reuse; their stories get a verified photo of the
   subject or go out as a **link post**, where Facebook's own preview shows the station's photo with the station's credit.
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
| Nov 20 | Parade of Lights (downtown Fort Worth) with a decorated boat from Lake Mead's Parade of Lights | the event name matched a file from another town | a generic event name (parade, festival, market, fair, run ...) must carry the city in the file name or title too; a local event with no picture of its own takes its venue (downtown at night) from the library |
| Nov 20 | San Antonio Zoo mourning a hippo's sweetheart with a USDA inspection of an ocelot at the same zoo | the zoo matched; the animal did not | when the headline names an animal, the photo's file name or title must carry it too (`animal_in`, alternatives like hippo/hippopotamus); otherwise the outlet story goes out as a link post |
| Nov 20 | 'Austin weekend: Theater performances, Bastrop B-day' with a Minneapolis theater | 'Theater' was taken as a subject, and the story was another city's calendar | a lone common noun is never a subject (`COMMON_NOUNS`); another metro's weekend roundup is dropped by the filter (`other_metro_roundup`) |
| Nov 20 | 'Why fall foliage looks different across South Central Texas' with a GOES storm image | the region was searched as a subject, and the story was another region's | regions are places (`PLACES`), never searched; another region's story is dropped by the filter (`other_region`) |
| Nov 20 | Texans' Chris Braswell carted off on the opening kickoff, with an aerial of NRG Stadium | the team's ground stood in for the play | a story about something that happened (`happened`) takes a picture from the event or none; outlet stories then go out as link posts with the outlet's photo; the stadium is never a stand-in |
| Nov 20 | Texas vs. Arkansas preview with an Unsplash landscape of Arkansas | the opponent's state name was searched as a subject | states are places (`PLACES`), never searched; a game preview with no picture of the team goes out as a link post |
| Nov 20 | The CONCACAF W tournament coming to Texas, with the 2012 U.S. women's team lifting a trophy | the team matched, fourteen years ago | a team or a person is shown only by a photo taken within three years and dated (`photo_age_bar`); otherwise the outlet story is a link post |
| Nov 20 | Nine of the day's eighteen posts went out as Facebook link posts (ESPN, WFAA, KXAN, NBC 5 ...) | the link preview shows the outlet's image and headline in a box: a post inside a post, not an original post | link posts are off (`link_when_no_photo: false`); a story with no picture of its subject that we may use is skipped |
| Nov 20 | A basketball showcase and a country concert at Dickies Arena with a K-pop concert photo | the file was titled "Twice - Dickies Arena" and the venue words matched | a venue is searched as a building (its category, "exterior", "building"); a photo of somebody else's show is never used for an event; the lesson row is in the fixture |
| Nov 21 | A Cowboys–Titans game preview with AT&T Stadium, under a caption that was the article's 2022 photo caption ("Dak Prescott (4) looks to pass ... at Nissan Stadium Thursday, Dec. 29, 2022") | the team name alone brought the home stadium, and the page's figure caption was scraped as the lead | a figure caption never becomes caption text (the article reader drops figures and asides; the writer drops jersey-number and wire-date sentences); a team name brings its home venue only for a game there: not when the text names another stadium or says the team is on the road |
| Nov 21 | KVUE's rolling Austin forecast page, retitled "What to expect across Texas as Thanksgiving travel gets underway", with the Fort Worth skyline, a caption that only said "Here are the latest updates from the KVUE Weather Impact Team" and a credit cut to "Billy Hathorn assumed (based on copyright c" | another metro's forecast slipped the region gate on the word Texas; the teaser line read as a sentence; a stored credit kept Commons boilerplate | another metro station's forecast page is dropped whatever the headline says; a station's teaser line is boilerplate; Commons' "assumed (based on copyright claims)" is removed from stored credits too, even when cut short |
| Nov 21 | A KXAN feature on Texas veterans and PTSD with a U.S. Navy "PTSD Awareness Month" poster, under a caption that was the headline alone | the Commons search for the acronym returned a graphic, and the feed gave no summary | a Commons file titled or credited as a graphic, infographic, flyer, banner or awareness poster is never a photo of the subject; an article whose feed gives no sentence to post is skipped, not posted as its headline |
| Nov 21 | "Bob on Business: Biz in the front, party in the back as One University Place breaks ground" with the developer's rendering credited to the Fort Worth Report | a column passed as news, and a courtesy rendering on the outlet's page was taken as its own photo | a title with a column label ("Name on Topic:", Opinion:, Commentary:, Editorial:) is dropped as a column; a source photo whose page caption says courtesy, rendering, handout or a wire agency is not the outlet's own and is not used |
| Nov 21 | "Parker disappointed Cowboys pulled play-calling duties" with a 2017 Cotton Bowl picture of AT&T Stadium, under a caption that was the page's Imagn photo caption ("Nov 15, 2026; Arlington, Texas, USA; ... looks on from the sidelines") | the team name brought the venue for a coaching story, and a caption block outside a figure was read as the lead | a venue is a picture only for a game or for itself, never for a coaching, roster or contract story; the article reader drops caption and credit blocks too; the dateline caption form and "Mandatory Credit" mark a photo caption |
| Nov 21 | CultureMap's weekly digest ("Portillo's closes 2 DFW restaurants and more top stories") with a Commons photo of a school farm in Peru named for a Coronel Pedro Portillo, under an "Editor's note" caption | a digest passed as a story, and the entity search for the chain's name matched a surname | a digest title (and more top stories, hottest headlines, news roundup) is dropped; an editor's note is boilerplate; a brand entity written with 's must match with its 's or as a business, never as a person's surname |
| Nov 21 | "Dallas Cowboys fan dies after altercation during 49ers game" with a caption about a Home Alone sequel, and Paxton's Tribune photo credited to the outlet instead of "Michael Cavazos for The Texas Tribune" | the page reader took the longest article block on the page (another story) and the caption's byline tail was not read as a credit | the story's block is the one that shares its title, and a body that shares none of the story's words is dropped; a caption ending "Name for Outlet" or "Name | Outlet" is the credit and goes on the card |
| Nov 21 | A Fort Worth Report profile of an Arlington teacher with a picture of an H-E-B store in Boerne | the body's sponsor line ("sponsored by Central Market, H-E-B and JPS Health Network") matched the H-E-B topic | a store named only in the body is never the picture (H-E-B is a headline-only topic); a series blurb and a sponsor line are boilerplate |
| Nov 21 | Fort Worth's e-bike rules with an AP archive photo of scooters in Los Angeles, credited "Damian Dovarganes \| AP archives" | the wire check knew "AP Photo" and "Associated Press" but not the agency's bare tag | an agency tag (AP, AFP, UPI, EPA) anywhere in the page caption or credit marks a wire photo, which is never taken |
| Nov 21 | Captions that read as cuts: "Democrat Clayton Tucker made that question part of his winning campaign" with the question dropped, and "At the meeting, the commission considered..." before any meeting was named | the writer dropped every question as columnist rhetoric, and the nut-graf swap did not know back-reference openers | a lede's question is kept when the next sentence refers to "that question" (and that sentence is dropped when the question is not there); an opener such as "At the meeting," goes after the sentence that names the meeting |
| Nov 21 | A Colleyville pet-resort story that recapped a Nov. 4 council meeting, published Nov. 21; and a homelessness caption that opened on "The city programs highlighted use $7 million..." and stated the $7 million twice | the writer had no age check on a recap's meeting date, and no guard against a nut graf or a repeated figure | a recap of a meeting more than a week before publication is skipped; "The ... programs highlighted" moves after the lead; a dollar figure already in the caption is not repeated |
| Nov 21 | "5 North Texas police officers among 30 nationwide honored by Justice Department" with a picture of UNT's Crumley Hall in Denton | the UNT library topic matched the words "North Texas", which name the region in almost every DFW headline | the UNT topic needs the university's name, "UNT" or "Mean Green"; "North Texas" alone never brings a campus |

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
