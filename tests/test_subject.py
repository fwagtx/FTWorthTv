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
    assert pairs[0][0][1] == () and pairs[0][0][2] == ("ty myers",)   # with Claude looking at the picture, the performer's own show may be a concert photo


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
