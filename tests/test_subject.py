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
        for topic in row.get("not_fallback", []):
            assert topic not in plan.fallback_topics, (row["title"], plan.fallback_topics, row["lesson"])
        for name in row.get("search", []):
            assert name in plan.search_names, (row["title"], plan.search_names)
        for name in row.get("not_search", []):
            assert name not in plan.search_names, (row["title"], plan.search_names, row["lesson"])
        for photo_title in row.get("rejected_photos", []):   # a found file the photo filters must refuse for this story
            from ftworthtv.images.providers import other_event_photo, unnamed_person_photo
            q = (plan.search_names or [""])[0]
            story_text = f"{row['title']} {row.get('body', '')}"
            assert other_event_photo(photo_title, q, story_text) or unnamed_person_photo(photo_title, q, story_text), \
                (row["title"], photo_title, row["lesson"])
        if "happened" in row:                      # an event: no library stand-in, a picture of it or a text card
            from ftworthtv.images.subject import happened
            assert happened(row["title"]) == row["happened"], (row["title"], row["lesson"])
        if row.get("not_photos"):                  # a library file that must never stand for this story in that month
            import random
            from ftworthtv.images.library import pick
            root = Path(__file__).resolve().parents[1]
            for seed in range(30):
                got = pick(root, row["library_topics"], month=row["month"], rng=random.Random(seed))
                assert got is None or str(got.path.relative_to(root)) not in row["not_photos"], (row["title"], got.path, row["lesson"])


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
    monkeypatch.setattr(providers, "_search_each", lambda q, s: iter([[show, bldg]]))
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
    monkeypatch.setattr(providers, "_search_each", lambda q, s: iter([[stranger, cobb, real]]))
    assert find_photo([("Ty Myers", (), ("ty myers",))], settings, None, fallback=False) is real
    monkeypatch.setattr(providers, "_search_each", lambda q, s: iter([[stranger, cobb]]))
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


def test_a_death_is_searched_by_the_person_only_and_an_honor_is_not_a_subject():
    """Render 119, Nov 22: 'Broncos Ring of Fame linebacker and Hall of Fame broadcaster Tom Jackson dies at 75' searched
    'Hall of Fame' (as a building) and drew another man at the San Jose Sports Hall of Fame induction."""
    from ftworthtv.images.subject import plan_subject
    plan = plan_subject("Broncos Ring of Fame linebacker and Hall of Fame broadcaster Tom Jackson dies at 75",
                        "Denver Broncos legend and Ring of Fame linebacker Tom Jackson has died at the age of 75.", "sports")
    assert plan.search_names == ["Tom Jackson"]
    assert "Hall of Fame" not in plan.entities


def test_results_written_as_losses_or_muscling_past_are_things_that_happened():
    """Render 120, Nov 22: 'Udoka says Rockets mentally fragile ... after loss to Nuggets' drew Toyota Center and 'Houston
    muscles past Kansas' drew the Houston skyline: neither was read as a result, so stand-ins were allowed."""
    from ftworthtv.images.subject import happened
    assert happened("Udoka says Rockets 'mentally fragile,' blasts defense after loss to Nuggets")
    assert happened("Houston muscles past Kansas to cap 3-day run, stamps claim to No. 1 ranking")
    assert not happened("Houston hosts Kansas on Saturday night")


def test_title_case_headlines_name_their_subjects():
    """Nov 23, render 155: Variety's "Tyson Fury Reveals Schizophrenia Diagnosis in Netflix Documentary" read as one name and
    'Netflix' in it gave the streaming topic (a TV remote). In a Title Case headline the story text says which words are names;
    without text, a headline verb ends the name."""
    fury = ("Tyson Fury Reveals Schizophrenia Diagnosis in Netflix Documentary: ‘I Thought I’d End Up in a Padded Room’",
            "Netflix’s feature-length documentary 'Tyson Fury' reveals that the boxer has been diagnosed with schizophrenia. "
            "The film will debut on Nov. 27, two weeks before Fury’s live Netflix bout against Anthony Joshua.")
    assert entities(*fury) == ["Tyson Fury", "Netflix"]
    plan = plan_subject(*fury, "culture")
    assert plan.primary == "Tyson Fury" and plan.mode == "search" and plan.fallback_topics == []
    assert subject_fits(*fury, "culture", "topic:streaming")[0] is False
    assert entities("Tyson Fury Reveals Schizophrenia Diagnosis In Netflix Doc") == ["Tyson Fury"]
    assert entities("TCU Falls to Utah in Home Finale", "The Horned Frogs lost to Utah 31-28 on Saturday at Amon G. Carter Stadium.") == ["TCU", "Utah"]
    assert entities("TCU Falls to Utah in Home Finale") == ["TCU", "Utah"]
    assert entities("Mahershala Ali Talks New Role in ‘Blade’ Reboot") == ["Mahershala Ali"]
    assert entities("Dickies Arena Hosts Big 12 Championship Game") == ["Dickies Arena"]
    # the platform as the subject keeps its category photo
    prices = plan_subject("Netflix Raises Prices Again in the US", "Netflix is raising the price of its plans in the United States, the company said.", "business")
    assert prices.mode == "institution" and prices.fallback_topics == ["streaming"]
    # a sentence-case headline is untouched
    assert entities("Fort Worth police set new policies for Flock cameras", "Flock cameras.") == ["Fort Worth police", "Flock"]


def test_attribution_is_only_a_trailing_source():
    """'..., Morath says' credits a source; 'Hailee Steinfeld confirms she's in Avengers' is about her (Nov 23)."""
    assert "Morath" not in entities("Largest enrollment drop in Texas' recorded history means challenges for public schools, Morath says", "Mike Morath said.")
    assert entities("Hailee Steinfeld Confirms She’s In ‘Avengers: Doomsday’", "Hailee Steinfeld has confirmed she will appear in Marvel's upcoming film, the actress said on Sunday.") == ["Hailee Steinfeld"]


def test_a_team_that_fires_a_coach_is_not_a_fire_department():
    """Nov 24, render 200: "Cardinals fire DC Rallis" drew a Fort Worth Fire Department rescue truck."""
    plan = plan_subject("Cardinals fire DC Rallis; Austin takes over on interim basis",
                        "The Cardinals have fired defensive coordinator Nick Rallis.", "sports")
    assert plan.primary == "Cardinals" and "fire" not in plan.fallback_topics and plan.mode != "institution"
    assert "fire" in plan_subject("Fort Worth Fire crews battle blaze at vacant house", "", "breaking").fallback_topics
    assert "police" in plan_subject("Fort Worth police set new policies for Flock cameras", "", "crime").fallback_topics


def test_residents_are_not_a_photo_subject():
    """Nov 24, render 201: "... jury duty scam targeting North Texans" searched photos of "North Texans"."""
    assert "North Texans" not in entities("Georgia prison inmates charged in $1 million jury duty scam targeting North Texans", "")
    from ftworthtv.images.subject import DEMONYM_RE
    assert not DEMONYM_RE.match("texans") and not DEMONYM_RE.match("houston texans")   # the team is still a subject


def test_a_bands_tour_photo_counts_as_context():
    """Nov 24, render 201: "U2 performing in Paris ... on Experience and Innocence Tour" lacked "bring", "greatest" and "world"."""
    from ftworthtv.images.subject import _context_words
    ctx = _context_words("U2 will bring 'Greatest Show' to Arlington on 2027 world tour", "U2")
    assert "tour" in ctx and "performing" in ctx and "concert" in ctx
    assert "tour" not in _context_words("CMA Awards nominees announced", "CMA")


def test_recent_years_are_searched_for_people_and_bands():
    """Nov 24, render 202: U2's photos inside the three-year bar (Sphere, Feb 2024) ranked below older files on Commons."""
    from datetime import datetime, timezone
    from ftworthtv.images.subject import with_recent_years
    stamp = datetime(2026, 11, 24, tzinfo=timezone.utc)
    pairs = [(("fresh:U2", ("statue",), ("u2",)), "entity:u2"), (("U2", ("statue",), ("u2",)), "entity:u2"),
             (("category:Dickies Arena", ("concert",), ()), "entity:dickies arena"), (("Dickies Arena", (), ()), "entity:dickies arena")]
    out = [q[0] for q, _ in with_recent_years(pairs, stamp)]
    assert out == ["fresh:U2", "U2", "commons:U2 2026", "commons:U2 2025", "commons:U2 2024", "category:Dickies Arena", "Dickies Arena"]
    assert with_recent_years(pairs, stamp)[2][0][1:] == (("statue",), ("u2",))       # the same checks on the file name


def test_commons_prefix_searches_commons_only(settings, monkeypatch):
    from ftworthtv.images import providers
    calls = []
    monkeypatch.setattr(providers, "search_openverse", lambda q, s=None, **k: (calls.append(("openverse", q)), [])[1])
    monkeypatch.setattr(providers, "search_wikimedia", lambda q, **k: (calls.append(("wikimedia", q)), [])[1])
    monkeypatch.setattr(providers, "_PROVIDERS_DOWN", set())
    monkeypatch.setattr(providers, "_search_started", [])
    assert providers._search("commons:U2 2024", settings) == []
    assert calls == [("wikimedia", "U2 2024")]


def test_a_band_photo_may_be_taken_in_another_city():
    """Nov 24, render 203: "U2 performing at Sphere in Las Vegas" carried "Nevada" and was refused for U2's Arlington show."""
    from datetime import datetime, timezone
    from ftworthtv.images import place_words
    stamp = datetime(2026, 11, 24, tzinfo=timezone.utc)
    avoid = ("houston", "nevada")
    assert place_words("entity:u2", stamp, avoid) == ()
    assert place_words("entity:dickies arena", stamp, avoid) == avoid          # a building keeps the other-city check
    assert place_words("beat:skyline", stamp, avoid) == avoid


def test_a_series_of_lawsuits_is_not_a_game():
    """Nov 24, render 203: "Paxton drops series of high-profile Texas lawsuits after election loss" read as a game result."""
    from ftworthtv.images.subject import happened
    assert not happened("Paxton drops series of high-profile Texas lawsuits after election loss")
    assert happened("Rangers drop series finale to Astros")


def test_a_teams_stadium_only_for_a_game_there():
    """Nov 24, render 206: "A wave of emotions for TCU after Dykes firing" drew an empty 2017 Amon G. Carter Stadium, and a Texas
    A&M season analysis drew Kyle Field: the sports-ground variant skipped the venue check, and Kyle Field was no venue."""
    assert "tcu-football" not in plan_subject("A wave of emotions for TCU after Dykes firing then a quick trip to No. 9 Texas Tech", "", "sports").entity_topics
    assert "tcu-football" in plan_subject("TCU hosts Baylor at Amon G. Carter Stadium in rivalry game", "", "sports").entity_topics
    assert plan_subject("One year after 11-0 start, Texas A&M enters rivalry week as a cautionary tale", "", "sports").entity_topics == []
    assert "texas-am" in plan_subject("Texas A&M hosts No. 5 Texas at Kyle Field in rivalry game", "", "sports").entity_topics


def test_a_board_or_party_is_an_institution_not_a_person():
    """Nov 24, render 207: "board of education" got the people-and-teams photo bar, so the other-city check was off and a
    Georgia county's board of education building went on the Texas State Board of Education story."""
    from datetime import datetime, timezone
    from ftworthtv.images import place_words
    from ftworthtv.images.subject import photo_age_bar
    stamp = datetime(2026, 11, 24, tzinfo=timezone.utc)
    for name in ("board of education", "texas dems", "texas cyber command"):
        assert photo_age_bar(f"entity:{name}", stamp) == ""
        assert place_words(f"entity:{name}", stamp, ("georgia",)) == ("georgia",)
    assert photo_age_bar("entity:u2", stamp) and photo_age_bar("entity:ken paxton", stamp)


def test_a_named_politician_is_searched_for_not_the_capitol():
    """Nov 24, render 208: "Paxton drops series of high-profile Texas lawsuits after election loss" drew the Texas Capitol; a
    bare surname takes the full name the story gives ("Ken Paxton"), never a namesake."""
    from ftworthtv.images.subject import full_name
    body = "After losing the election, Attorney General Ken Paxton and his office have dropped a series of high-profile lawsuits."
    sp = plan_subject("Paxton drops series of high-profile Texas lawsuits after election loss", body, "politics")
    assert sp.primary == "Ken Paxton" and "capitol" not in sp.entity_topics
    assert full_name("Paxton", "Attorney General Paxton said.") == "Paxton"           # no first name in the story: unchanged
    assert full_name("TCU", "TCU fans cheered.") == "TCU"
    assert "capitol" in plan_subject("Texas lawmakers file bill to cut property taxes", "", "politics").entity_topics + \
        plan_subject("Texas lawmakers file bill to cut property taxes", "", "politics").fallback_topics


def test_quote_marks_do_not_hide_a_named_subject():
    """Nov 24, render 210: "entity:toys r us" against "Toys 'R' Us opens only standalone store in Fort Worth" was held."""
    from ftworthtv.images.subject import subject_fits
    assert subject_fits("Iconic toy retailer Toys 'R' Us opens only standalone store in Fort Worth", "", "business", "entity:toys r us")[0]
    assert not subject_fits("Iconic toy retailer opens only standalone store in Fort Worth", "", "business", "entity:toys r us")[0]


def test_a_columns_name_before_the_colon_is_not_a_subject():
    """Nov 25: the Fort Worth Report's "The Dish: Acquolina brings Italian fare to the slopes of Camp Bowie District" searched
    "Dish" and drew a 16th-century enamel dish in the British Museum."""
    from ftworthtv.images.subject import plan_subject
    plan = plan_subject("The Dish: Acquolina brings Italian fare to the slopes of Camp Bowie District",
                        "Next winter, thanks to Acquolina bringing its wood-fired pizzas to Fort Worth.", "business")
    assert "Dish" not in plan.search_names and "Acquolina" in plan.search_names
    assert "TCU" in plan_subject("TCU: Frogs fall to Baylor 70-62", "TCU lost to Baylor.", "sports").search_names


def test_a_teams_short_name_names_it_and_its_visits_are_not_its_games():
    """Nov 26, renders 266 and 269: "Cowboys vs. Eagles: Thanksgiving game info ..." was held ("headline no longer names
    'dallas cowboys'") and its picture was "Dallas Cowboys Players and Cheerleaders Visit Fort Sill"."""
    from ftworthtv.images.subject import plan_subject, provider_queries, subject_fits
    title = "Cowboys vs. Eagles: Thanksgiving game info, halftime show and national anthem singers"
    body = "The Dallas Cowboys host the Philadelphia Eagles on Thanksgiving."
    assert subject_fits(title, body, "sports", "entity:dallas cowboys")[0] is True
    assert subject_fits("Utah visits TCU, close to Big 12 title game", "", "sports", "entity:dallas cowboys")[0] is False
    pairs = provider_queries(plan_subject(title, body, "sports"), title, "sports")
    team = [q for q, lab in pairs if lab == "entity:dallas cowboys"]
    assert team and all("visit" in q[1] for q in team)
    visit = "Cowboys players visit Cook Children's patients on Thanksgiving week"
    pairs = provider_queries(plan_subject(visit, "The Dallas Cowboys visited patients.", "sports"), visit, "sports")
    assert all("visit" not in q[1] for q, lab in pairs if lab == "entity:dallas cowboys")
