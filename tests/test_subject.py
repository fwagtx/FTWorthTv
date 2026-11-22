from ftworthtv.images.subject import entities, plan_subject, subject_fits


def test_headline_subjects():
    assert entities("Anthropic's $81.3 billion IPO is the largest ever; shares open at $111.50 on the Nasdaq", "Anthropic raised money.") == ["Anthropic", "Nasdaq"]
    assert entities("Largest enrollment drop in Texas' recorded history means challenges for public schools, Morath says", "Mike Morath said.") == ["Texas"]
    assert entities("Northwest ISD approves revised high school boundaries after parents speak out") == ["Northwest ISD"]
    assert entities("Fort Worth police set new policies for Flock cameras", "Flock cameras.") == ["Fort Worth police", "Flock"]


def test_plan_picks_the_subject_not_the_venue():
    ipo = plan_subject("Anthropic's $81.3 billion IPO is the largest ever; shares open at $111.50 on the Nasdaq", "Anthropic raised $81.3 billion.", "business")
    assert ipo.mode == "entity" and ipo.primary == "Anthropic" and ipo.entity_topics == ["anthropic"]   # never the exchange building
    tcu = plan_subject("Utah visits TCU, close to Big 12 title game", "Utah comes to Fort Worth.", "sports")
    assert tcu.mode == "entity" and tcu.entity_topics[0] == "tcu-football"
    isd = plan_subject("Northwest ISD approves revised high school boundaries after parents speak out", "", "community")
    assert isd.mode == "entity" and isd.entity_topics == ["northwest-isd"]
    schools = plan_subject("Largest enrollment drop in Texas' recorded history means challenges for public schools, Morath says", "Mike Morath said.", "community")
    assert schools.mode == "beat"
    gta = plan_subject("Grand Theft Auto VI is out today on PS5 and Xbox", "", "culture")
    assert gta.mode == "institution" and gta.fallback_topics == ["gaming"]
    dallas = plan_subject("Voters will likely decide Dallas City Hall's future in May election", "", "politics")
    assert dallas.mode == "search" and dallas.search_names == ["Dallas City Hall"]        # Fort Worth City Hall must not stand in
    flock = plan_subject("Fort Worth police set new policies for Flock cameras", "Flock cameras.", "crime")
    assert flock.mode == "institution" and flock.fallback_topics == ["police"]


def test_publish_time_check_rejects_a_photo_that_rhymes_with_the_story():
    title, body = "Anthropic's $81.3 billion IPO is the largest ever; shares open at $111.50 on the Nasdaq", "Anthropic raised $81.3 billion."
    assert subject_fits(title, body, "business", "beat:stock-market")[0] is False
    assert subject_fits(title, body, "business", "topic:anthropic")[0] is True
    assert subject_fits(title, body, "business", "entity:anthropic")[0] is True
    assert subject_fits(title, body, "business", None)[0] is False
    assert subject_fits("Utah visits TCU, close to Big 12 title game", "", "sports", "topic:tcu-football")[0] is True
    assert subject_fits("Utah visits TCU, close to Big 12 title game", "", "sports", "topic:tcu")[0] is True
    assert subject_fits("Utah visits TCU, close to Big 12 title game", "", "sports", "beat:skyline")[0] is False


def test_pipeline_records_the_subject_and_holds_a_mismatch(settings, now):
    from datetime import timedelta
    from ftworthtv.checks import preflight
    from ftworthtv.models import Story
    from ftworthtv.pipeline import run
    tcu = Story(id="t1", source="NBC 5 DFW", source_kind="rss", title="Utah visits TCU, close to Big 12 title game",
                summary="No. 2 Utah comes to Fort Worth on Saturday night and can clinch a spot in the Big 12 championship game with a win over TCU.",
                url="https://example.com/tcu", published=now - timedelta(hours=2), category_hint="sports", extra={"scope": "local"})
    ant = Story(id="a1", source="CBS News", source_kind="rss", title="Anthropic's $81.3 billion IPO is the largest ever; shares open at $111.50 on the Nasdaq",
                summary="Anthropic raised $81.3 billion as part of its IPO. Shares opened at $111.50 on the Nasdaq.",
                url="https://example.com/ant", published=now - timedelta(hours=1), category_hint="business", extra={"scope": "national", "national": True}, always_relevant=True)
    settings.max_posts = 2
    report = run(settings, now=now, stories=[tcu, ant], publisher_name="dryrun")
    by = {d.story.id: d for d in report.drafts}
    assert by["t1"].image.subject == "topic:tcu-football" and "tcu-football" in str(by["t1"].image.path.name or "") or "amon-g-carter" in str(by["t1"].image.photo_id)
    assert "a1" not in by and any(st.id == "a1" and why == "no picture of the subject that we may use" for st, why in report.skipped)
    # no verified Anthropic photo offline: no post at all, never the Nasdaq tower and never a link preview
    assert preflight(by["t1"], network=False) == []
    by["t1"].image.subject = "beat:stock-market"
    assert any("photo does not show the subject" in p for p in preflight(by["t1"], network=False))


def test_headline_lessons_fixture():
    """Every mistake the page has made becomes a row here; the planner must keep getting them right."""
    import json
    from pathlib import Path
    rows = json.loads((Path(__file__).parent / "fixtures" / "headline_subjects.json").read_text(encoding="utf-8"))
    assert len(rows) >= 10
    for row in rows:
        plan = plan_subject(row["title"], row.get("body", ""), row["category"])
        assert plan.mode == row["mode"], (row["title"], plan.mode, row["lesson"])
        for topic in row.get("topics", []):
            assert topic in plan.entity_topics, (row["title"], plan.entity_topics)
        for topic in row.get("not_topics", []):
            assert topic not in plan.entity_topics, (row["title"], plan.entity_topics, row["lesson"])
        if row.get("first_topic"):
            assert plan.entity_topics[0] == row["first_topic"], (row["title"], plan.entity_topics)
        for topic in row.get("fallback", []):
            assert topic in plan.fallback_topics, (row["title"], plan.fallback_topics)
        for name in row.get("search", []):
            assert name in plan.search_names, (row["title"], plan.search_names)
        for name in row.get("not_search", []):
            assert name not in plan.search_names, (row["title"], plan.search_names, row["lesson"])


def test_a_venue_is_searched_as_a_building_not_as_someone_elses_show():
    from ftworthtv.images.subject import plan_subject, provider_queries
    plan = plan_subject("Women's Funkytown Showdown at Dickies Arena, Sun, Nov 22 12:00 PM", "", "sports")
    pairs = provider_queries(plan, "Women's Funkytown Showdown at Dickies Arena, Sun, Nov 22 12:00 PM", "sports")
    venue = [q for q, lab in pairs if lab == "entity:dickies arena"]
    assert venue and venue[0][0] == "category:Dickies Arena" and "concert" in venue[0][1] and "k-pop" in venue[0][1]
    assert all(("dickies arena",) == q[2] for q in venue)
    ipo = plan_subject("Anthropic's $81.3 billion IPO is the largest ever", "Anthropic raised money.", "business")
    pairs = provider_queries(ipo, "Anthropic's $81.3 billion IPO is the largest ever", "business")
    assert pairs[0][0][0] == "fresh:Anthropic" and "concert" in pairs[0][0][1] and pairs[0][0][2] == ("anthropic",)
    concert = plan_subject("Ty Myers: The Legal Tour 2026 at Dickies Arena", "", "events")
    pairs = provider_queries(concert, "Ty Myers: The Legal Tour 2026 at Dickies Arena", "events")
    assert all("ty myers" not in q[2] for q, _ in pairs)               # a person is never searched for without the visual check
    assert pairs[0][0][0] == "category:Dickies Arena"
    pairs = provider_queries(concert, "Ty Myers: The Legal Tour 2026 at Dickies Arena", "events", people_allowed=True)
    assert "concert" not in pairs[0][0][1] and pairs[0][0][2] == ("ty myers",)   # with Claude looking at the picture, the performer's own show may be a concert photo
    assert "statue" in pairs[0][0][1]                                  # but a statue of a performer is not the performer


def test_find_photo_skips_a_show_photo_when_the_story_is_the_building(monkeypatch, settings):
    from ftworthtv.images import providers
    from ftworthtv.images.providers import PhotoCandidate, find_photo
    show = PhotoCandidate(id="c1", url="https://x/1.jpg", credit="c", license="wikimedia-cc", provider="wikimedia",
                          source_url="https://commons.wikimedia.org/w/index.php?curid=1", width=2000, height=1300, alt="TWICE World Tour at Dickies Arena")
    bldg = PhotoCandidate(id="c2", url="https://x/2.jpg", credit="c", license="wikimedia-cc", provider="wikimedia",
                          source_url="https://commons.wikimedia.org/wiki/File:Dickies_Arena_exterior.jpg", width=2000, height=1300, alt="Dickies Arena exterior")
    monkeypatch.setattr(providers, "_search", lambda q, s: [show, bldg])
    got = find_photo([("category:Dickies Arena", providers.PERFORMANCE_WORDS, ("dickies arena",))], settings, None, fallback=False)
    assert got is bldg


def test_a_description_mention_is_not_a_photo_of_the_subject(monkeypatch, settings):
    from ftworthtv.images import providers
    from ftworthtv.images.providers import PhotoCandidate, find_photo
    stranger = PhotoCandidate(id="c1", url="https://x/1.jpg", credit="c", license="wikimedia-cc", provider="wikimedia",
                              source_url="https://commons.wikimedia.org/wiki/File:LarryBennese.JPG", width=2000, height=1300,
                              alt="Larry Bennese, who once opened for Ty Myers", title="LarryBennese")
    real = PhotoCandidate(id="c2", url="https://x/2.jpg", credit="c", license="wikimedia-cc", provider="wikimedia",
                          source_url="https://commons.wikimedia.org/wiki/File:Ty_Myers_2025.jpg", width=2000, height=1300, alt="", title="Ty Myers 2025")
    cobb = PhotoCandidate(id="c3", url="https://x/3.jpg", credit="c", license="wikimedia-cc", provider="wikimedia",
                          source_url="https://commons.wikimedia.org/wiki/File:Ty_Cobb_at_Fort_Myers.jpg", width=2000, height=1300, alt="",
                          title="Ty Cobb, Thomas Edison, and Connie Mack at a Fort Myers baseball park")
    monkeypatch.setattr(providers, "_search", lambda q, s: [stranger, cobb, real])
    assert find_photo([("Ty Myers", (), ("ty myers",))], settings, None, fallback=False) is real
    monkeypatch.setattr(providers, "_search", lambda q, s: [stranger, cobb])
    assert find_photo([("Ty Myers", (), ("ty myers",))], settings, None, fallback=False) is None


def test_people_and_recent_pictures():
    from ftworthtv.images.subject import looks_like_person, wants_recent_picture
    assert looks_like_person("Ty Myers") and looks_like_person("Cooper Flagg") and looks_like_person("Bo French")
    assert not looks_like_person("Dickies Arena") and not looks_like_person("Northwest ISD") and not looks_like_person("Dallas Cowboys")
    assert wants_recent_picture("Utah visits TCU in Saturday's game", "sports") and wants_recent_picture("Parade of Lights returns downtown", "events")
    assert not wants_recent_picture("Property tax rate set for next year", "politics")


def test_a_generic_event_name_needs_the_city_in_the_photo_name():
    from ftworthtv.images.subject import is_generic_event, plan_subject, provider_queries
    title = "Parade of Lights rolls through downtown Fort Worth this Sunday"
    plan = plan_subject(title, "", "events")
    assert is_generic_event("Parade of Lights") and not is_generic_event("Anthropic")
    pairs = [(q, label) for q, label in provider_queries(plan, title, "events", people_allowed=True, city="Fort Worth") if label == "entity:parade of lights"]
    assert pairs and all("fort worth" in q[2] for q, _ in pairs)          # "Parade of Lights" alone matched Lake Mead's boat parade
    pairs = [(q, label) for q, label in provider_queries(plan, title, "events", people_allowed=True, city="") if label == "entity:parade of lights"]
    assert pairs and all("fort worth" not in q[2] for q, _ in pairs)      # a non-local story is not forced to Fort Worth


def test_a_zoo_story_needs_the_animal_in_the_photo_name():
    from ftworthtv.images.subject import animal_in, plan_subject, provider_queries
    title = "One last love letter: San Antonio Zoo mourns Fiona, Timothy the hippo's longtime sweetheart"
    assert animal_in(title).startswith("hippo") and animal_in("Fort Worth council approves budget") == ""
    plan = plan_subject(title, "", "culture")
    pairs = [q for q, label in provider_queries(plan, title, "culture", people_allowed=True) if label == "entity:san antonio zoo"]
    assert pairs and all(any(w.startswith("hippo") for w in q[2]) for q in pairs)   # an ocelot on an operating table is not the story


def test_a_thing_that_happened_is_recognised():
    from ftworthtv.images.subject import happened
    assert happened("Braswell, in debut for Texans, carted off with knee injury on opening kickoff")
    assert happened("Cooper Flagg scores 33 as Mavs keep Warriors winless since Curry's injury")
    assert happened("Crash shuts down northbound I-35W near downtown")
    assert not happened("No. 2 Utah visits TCU on Saturday night, one win from the Big 12 title game")
    assert not happened("Parade of Lights rolls through downtown Fort Worth this Sunday", "culture")
    assert not happened("Fort Worth police searching for Kenneth Gaines", "wanted")


def test_a_ballot_label_is_not_a_photo_subject():
    from ftworthtv.images.subject import entities, plan_subject
    assert "Prop J" not in entities("Austin voter files lawsuit challenging approved Prop J")
    plan = plan_subject("Texas House District 61 race margin is just seven votes; recount filed with state", "", "politics")
    assert "District 61" not in plan.search_names


def test_a_team_or_person_photo_must_be_recent_and_dated():
    from datetime import datetime, timezone
    from ftworthtv.images.subject import photo_age_bar
    stamp = datetime(2026, 11, 20, tzinfo=timezone.utc)
    assert photo_age_bar("entity:uswnt", stamp) == "2023-11-21"          # a 2012 trophy lift is not the 2026 team
    assert photo_age_bar("entity:ty myers", stamp) == "2023-11-21"
    assert photo_age_bar("entity:dickies arena", stamp) == ""             # a building keeps its file photo
    assert photo_age_bar("entity:northwest isd", stamp) == ""
    assert photo_age_bar("beat:skyline", stamp) == ""


def test_a_conviction_is_a_thing_that_happened():
    from ftworthtv.images.subject import happened
    assert happened("North Texas man convicted of defrauding $6M from 70 churches, congregants")
    assert happened("Fort Worth pastor pleads guilty to wire fraud")


def test_a_brand_written_with_s_is_searched_as_the_brand_not_a_surname():
    from ftworthtv.images.subject import plan_subject, provider_queries
    title = "Hot dog chain Portillo's closes 2 DFW restaurants"
    plan = plan_subject(title, "", "food")
    pairs = [q for q, label in provider_queries(plan, title, "food") if label == "entity:portillo"]
    assert pairs and all(q[2] == ("portillo's|portillo’s|portillos",) for q in pairs)     # a Commons file named for a Coronel Pedro Portillo must not match
    ipo = "Anthropic's $81.3 billion IPO is the largest ever"
    pairs = [q for q, label in provider_queries(plan_subject(ipo, "", "business"), ipo, "business") if label == "entity:anthropic"]
    assert pairs and all(q[2] == ("anthropic",) for q in pairs)                           # an ordinary possessive keeps the plain name


def test_a_team_name_reaches_its_stadium_only_for_a_game_there():
    from ftworthtv.images.subject import plan_subject
    charity = plan_subject("Dallas Cowboys mark 30 years of giving back with Salvation Army",
                           "The Dallas Cowboys celebrated 30 years of partnership with the Salvation Army by serving early "
                           "Thanksgiving meals at facilities in Dallas and Fort Worth.", "sports")
    assert "att-stadium" not in charity.entity_topics            # Nov 21: a Wisconsin bowl game at AT&T Stadium was the picture
    game = plan_subject("Cowboys host Eagles at AT&T Stadium on Thanksgiving", "Kickoff is at 3:30 p.m. in Arlington.", "sports")
    assert "att-stadium" in game.entity_topics


def test_team_nicknames_are_searched_by_the_full_team_name_and_teams_age():
    from datetime import datetime, timezone
    from ftworthtv.images.subject import photo_age_bar, plan_subject, provider_queries
    title = "Kyrie Irving scores 25, Cooper Flagg 22 as the Mavericks top the Clippers 110-100"
    plan = plan_subject(title, "Kyrie Irving scored 25 points and Cooper Flagg had 22 points.", "sports")
    assert "uta" not in plan.entity_topics and "uta-sports" not in plan.entity_topics      # the UTA Mavericks are a college team
    queries = [q[0] for q, _ in provider_queries(plan, title, "sports")]
    assert any("Dallas Mavericks" in q for q in queries)                                    # never OS X Mavericks
    assert not any("Clippers" in q for q in queries)                                        # a bare nickname finds hair clippers
    now = datetime(2026, 11, 22, tzinfo=timezone.utc)
    assert photo_age_bar("entity:dallas cowboys", now) == "2023-11-23"                      # a 2010 Romo wallpaper is not the 2026 team
    assert photo_age_bar("entity:dickies arena", now) == "" and photo_age_bar("entity:fort worth isd", now) == ""
    assert "uta" in plan_subject("UTA Mavericks beat Abilene Christian in overtime", "", "sports").entity_topics


def test_a_school_in_a_sports_headline_is_searched_as_its_team_and_artworks_are_not_news_photos():
    """Render 107, Nov 21: "Notre Dame loses safety Talich to injury during SMU's opening drive" found Notre-Dame de Paris;
    "Dallas Cowboys mark 30 years of giving back with Salvation Army" found a bronze Salvation Army memorial relief."""
    from ftworthtv.images.subject import plan_subject, provider_queries
    title = "Notre Dame loses safety Talich to injury during SMU's opening drive"
    pairs = provider_queries(plan_subject(title, "Notre Dame starting safety Luke Talich left the game.", "sports"), title, "sports",
                             people_allowed=True)                  # the render runs with the session reviewing every card
    nd = [q for q, lab in pairs if lab == "entity:notre dame"]
    assert nd and all(any("football" in w for w in q[2]) for q in nd)        # the file must say football (or another sport word)
    title = "Dallas Cowboys mark 30 years of giving back with Salvation Army"
    pairs = provider_queries(plan_subject(title, "The Cowboys served Thanksgiving meals with the Salvation Army.", "sports"), title, "sports")
    assert all("sculpture" in q[1] and "relief" in q[1] and "memorial" in q[1] for q, _ in pairs)
    cowboys = [q for q, lab in pairs if lab == "entity:dallas cowboys"]
    assert cowboys and all(q[2] == ("dallas cowboys",) for q in cowboys)      # a full team name needs no sport word
    statue = "Fort Worth unveils a statue of Bill Pickett at the Stockyards"
    pairs = provider_queries(plan_subject(statue, "", "community"), statue, "community")
    assert all("statue" not in q[1] for q, _ in pairs)                         # the statue is the story here


def test_a_title_and_surname_is_searched_by_the_full_name_and_adjectives_are_not_subjects():
    """Render 108, Nov 22: "Senator Cruz launches Saving Texas to win back the State House and some Congressional seats"
    was searched as "Senator Cruz" (no file is named that) and "Congressional", which found an unnamed congressman's portrait."""
    from ftworthtv.images.subject import plan_subject, resolve_titled
    title = "Senator Cruz launches Saving Texas to win back the State House and some Congressional seats in 2028"
    body = "Following the blue wave election in Texas, U.S. Senator Ted Cruz pledges to recapture the State House."
    plan = plan_subject(title, body, "politics")
    assert "Ted Cruz" in plan.search_names and "Congressional" not in plan.search_names and "Senator Cruz" not in plan.search_names
    assert resolve_titled("Mayor Parker", "Fort Worth Mayor Mattie Parker said Monday ...") == "Mattie Parker"
    assert resolve_titled("Senator Cruz", "The senator spoke Monday.") is None          # a bare surname finds strangers
    assert resolve_titled("Kyrie Irving", "") == "Kyrie Irving"


def test_a_game_result_headline_is_something_that_happened():
    """Render 109, Nov 22: "TCU Falls to Utah in Home Finale" was not read as a result and went out (in review) with an
    empty Amon G. Carter Stadium from 2017; a result takes a picture of the game or none."""
    from ftworthtv.images.subject import happened
    for title in ("TCU Falls to Utah in Home Finale", "TCU Pushes Past Kansas State, 20-10", "Mavericks top the Clippers 110-100",
                  "Stars edge Blues in shootout", "Rangers drop series finale to Astros", "Horned Frogs come up short against Baylor"):
        assert happened(title), title
    assert not happened("Frogs Host No. 2 Utah Under the Lights on Saturday")        # a preview may show the stadium


def test_a_cloudy_forecast_gets_a_gray_sky_and_sunshine_photos_are_sunny():
    import json
    from pathlib import Path
    from ftworthtv.images.subject import weather_topics
    assert weather_topics("Fort Worth forecast for Sunday, November 22 Mostly Cloudy")[0] == "clouds"
    assert weather_topics("Fort Worth forecast Partly Cloudy")[0] == "sunshine"
    lib = json.loads((Path(__file__).parents[1] / "assets" / "photos" / "library.json").read_text(encoding="utf-8"))
    clouds = {e["file"] for e in lib if e["topic"] == "clouds"}
    sunny = {e["file"] for e in lib if e["topic"] == "sunshine"}
    assert clouds and not (clouds & sunny)              # the gray courthouse photo is never a sunshine picture


def test_a_letter_grade_or_a_generic_word_is_not_a_subject():
    """Render 114, Nov 22: "College football grades: Texas earns 'A' ..., Indiana gets 'D'" kept "D" as a name, and "D" sat
    inside nearly every topic phrase, so the plan offered Dickies Arena, AT&T Stadium, Stars ice ... and drew AT&T Stadium."""
    from ftworthtv.images.subject import plan_subject
    plan = plan_subject("College football grades: Texas earns 'A' for dominant win, Indiana gets 'D' on Week 12 report card",
                        "When Texas quarterback Arch Manning takes care of the football ...", "sports")
    assert "D" not in plan.entities and "College" not in plan.entities
    assert "att-stadium" not in plan.entity_topics and "dickies-arena" not in plan.entity_topics


def test_a_quoted_work_title_is_not_mined_for_words():
    """Render 118, Nov 22: "'Hunger Games: Sunrise on the Reaping' Slays $120M at Box Office" searched "Sunrise" and drew
    a sunrise over a mosque."""
    from ftworthtv.images.subject import plan_subject
    plan = plan_subject("‘Hunger Games: Sunrise on the Reaping’ Slays $120M at Box Office as Franchise Heats Back Up",
                        "The sixth film in the Lionsgate series rebounded.", "culture")
    assert not any("sunrise" in n.lower() for n in plan.entities) and "Box Office" not in plan.entities
