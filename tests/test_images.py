from PIL import Image

from ftworthtv.images.card import placeholder_background, render_card


def test_render_card_with_placeholder(settings, tmp_path):
    out = render_card(background=None, headline="Crash shuts down northbound I-35W near downtown Fort Worth",
                      category_label="TRAFFIC", brand=settings.brand, out_path=tmp_path / "card.jpg", fonts_dir=settings.fonts_dir,
                      source_line="Source: Fort Worth Report", photo_credit=None, subline="Morning rush")
    with Image.open(out) as im:
        assert im.size == (1080, 1350) and im.format == "JPEG"


def test_render_card_contain_mode_with_photo(settings, tmp_path):
    photo = tmp_path / "radar.png"
    Image.new("RGB", (600, 550), (30, 120, 60)).save(photo)
    out = render_card(background=photo, headline="Severe Thunderstorm Warning until 7:30 PM", category_label="WEATHER ALERT",
                      brand=settings.brand, out_path=tmp_path / "radar-card.jpg", fonts_dir=settings.fonts_dir, fit="contain",
                      photo_credit="Radar: NWS Fort Worth (public domain)", size=(1080, 1080))
    with Image.open(out) as im:
        assert im.size == (1080, 1080)


def test_placeholder_is_deterministic(settings):
    a = placeholder_background((200, 250), settings.brand["colors"], seed="x")
    b = placeholder_background((200, 250), settings.brand["colors"], seed="x")
    assert a.tobytes() == b.tobytes()


def test_photo_family_treats_crops_as_the_same_photo():
    from ftworthtv.images.providers import PhotoCandidate
    a = PhotoCandidate(id="commons-1", url="", credit="", license="", provider="wikimedia",
                       source_url="https://commons.wikimedia.org/wiki/File:Twice_-_Dickies_Arena,_2022.jpg")
    b = PhotoCandidate(id="commons-2", url="", credit="", license="", provider="wikimedia",
                       source_url="https://commons.wikimedia.org/wiki/File:Twice_-_Dickies_Arena,_2022_(cropped).jpg")
    assert a.family == b.family



def test_render_plain_keeps_aspect_and_adds_watermark(settings, tmp_path):
    from ftworthtv.images.card import render_plain
    photo = tmp_path / "mug.png"
    Image.new("RGB", (288, 432), (120, 160, 200)).save(photo)
    out = render_plain(photo, tmp_path / "plain.jpg", brand=settings.brand, fonts_dir=settings.fonts_dir, watermark="@FortWorthTexasTV")
    with Image.open(out) as im:
        assert im.format == "JPEG" and min(im.size) >= 720 and abs(im.width / im.height - 288 / 432) < 0.01


def test_commons_author_cleanup_and_category_parsing():
    from ftworthtv.images.providers import _candidates_from_pages, _clean_artist
    assert _clean_artist("No machine-readable author provided. Tokoroten assumed (based on copyright claims).") == "Tokoroten"
    assert _clean_artist("<a href='x'>Jane Doe</a>") == "Jane Doe"
    payload = {"query": {"pages": [{"pageid": 1, "title": "File:Dickies Arena exterior.jpg", "imageinfo": [{
        "thumburl": "https://upload.wikimedia.org/x.jpg", "width": 2000, "height": 1300, "descriptionurl": "https://commons.wikimedia.org/wiki/File:Dickies_Arena_exterior.jpg",
        "extmetadata": {"LicenseShortName": {"value": "CC BY-SA 4.0"}, "Artist": {"value": "Someone"}}}]},
        {"pageid": 2, "title": "File:Venue map.svg", "imageinfo": [{"thumburl": "https://upload.wikimedia.org/m.png", "width": 2000, "height": 2000,
        "extmetadata": {"LicenseShortName": {"value": "CC0"}}}]}]}}
    cands = _candidates_from_pages(payload)
    assert len(cands) == 1 and cands[0].credit == "Photo: Someone via Wikimedia Commons (CC BY-SA 4.0)"


def test_alternative_photo_providers_parse_their_payloads():
    from ftworthtv.images.providers import parse_flickr, parse_openverse, parse_pixabay, parse_unsplash
    u = parse_unsplash({"results": [{"id": "abc", "width": 4000, "height": 6000, "alt_description": "Fort Worth skyline",
                                      "urls": {"regular": "https://images.unsplash.com/x?w=1080"}, "user": {"name": "Jane"},
                                      "links": {"html": "https://unsplash.com/photos/abc", "download_location": "https://api.unsplash.com/photos/abc/download"}}]})
    assert u[0].credit == "Photo: Jane on Unsplash" and u[0].download_hook.endswith("/download") and u[0].provider == "unsplash"
    px = parse_pixabay({"hits": [{"id": 7, "largeImageURL": "https://pixabay.com/get/x.jpg", "user": "bob", "pageURL": "https://pixabay.com/photos/7", "imageWidth": 1920, "imageHeight": 1280, "tags": "fort worth, texas"}]})
    assert px[0].id == "pixabay-7" and "via Pixabay" in px[0].credit
    ov = parse_openverse({"results": [
        {"id": "1", "url": "https://live.staticflickr.com/a.jpg", "license": "by", "license_version": "2.0", "creator": "Ann", "source": "flickr", "width": 2048, "height": 1365, "foreign_landing_url": "https://flickr.com/p/1", "title": "Stockyards"},
        {"id": "2", "url": "https://x/b.jpg", "license": "by-nc", "creator": "Nope", "source": "flickr", "width": 2048, "height": 1365}]})
    assert len(ov) == 1 and ov[0].credit == "Photo: Ann (CC BY 2.0) via Flickr" and ov[0].license == "openverse-cc"
    fl = parse_flickr({"photos": {"photo": [
        {"id": "9", "owner": "o1", "ownername": "Cal", "license": "4", "url_l": "https://live.staticflickr.com/9_b.jpg", "width_l": 1024, "height_l": 768, "title": "TCU"},
        {"id": "10", "owner": "o2", "ownername": "Dee", "license": "0", "url_l": "https://live.staticflickr.com/10_b.jpg"}]}})
    assert len(fl) == 1 and fl[0].credit == "Photo: Cal (CC BY 2.0) via Flickr" and fl[0].source_url == "https://www.flickr.com/photos/o1/9"


def test_provider_chain_falls_through_to_keyless_providers(settings, monkeypatch):
    from ftworthtv.images import providers
    calls = []
    monkeypatch.setattr(providers, "search_openverse", lambda q, s=None, **k: (calls.append("openverse"), [])[1])
    monkeypatch.setattr(providers, "search_wikimedia", lambda q, **k: (calls.append("wikimedia"), [providers.PhotoCandidate(id="commons-1", url="u", credit="c", license="wikimedia-cc", provider="wikimedia", source_url="s")])[1])
    settings.pexels_api_key = settings.unsplash_access_key = settings.flickr_api_key = settings.pixabay_api_key = None
    found = providers._search("Fort Worth skyline", settings)
    assert calls == ["openverse", "wikimedia"] and found[0].provider == "wikimedia"


def test_unsafe_photos_are_filtered(settings, monkeypatch):
    from ftworthtv.images import providers
    bad = providers.PhotoCandidate(id="openverse-1", url="https://x/a.jpg", credit="Photo: A", license="openverse-cc", provider="openverse",
                                   source_url="https://flickr.com/p/1", alt="Lingerie Football League game")
    good = providers.PhotoCandidate(id="openverse-2", url="https://x/b.jpg", credit="Photo: B", license="openverse-cc", provider="openverse",
                                    source_url="https://flickr.com/p/2", alt="AT&T Stadium exterior")
    monkeypatch.setattr(providers, "_search_each", lambda q, s: iter([[bad, good]]))
    assert providers.find_photo("football stadium Texas", settings).id == "openverse-2"


def test_quote_card_renders_with_and_without_photo(settings, tmp_path):
    from ftworthtv.images.card import render_quote_card
    photo = tmp_path / "p.jpg"
    Image.new("RGB", (1200, 800), (90, 120, 160)).save(photo)
    out = render_quote_card(author="Fort Worth Police Department", handle="@fortworthpd", when="2h", text="WANTED: Sample Person\nWanted for aggravated robbery.",
                            photo=photo, out_path=tmp_path / "q.jpg", brand=settings.brand, fonts_dir=settings.fonts_dir, watermark="@FortWorthTexasTV",
                            footer="Source: police.fortworthtexas.gov")
    with Image.open(out) as im:   # width is fixed, height follows the card between square and 4:5
        assert im.width == 1080 and 1080 <= im.height <= 1350
    out2 = render_quote_card(author="Fort Worth Report", handle="@FortWorthReport", when="Nov 18", text="A headline with no photo at all " * 4,
                             photo=None, out_path=tmp_path / "q2.jpg", brand=settings.brand, fonts_dir=settings.fonts_dir)
    assert out2.exists()


def test_quoted_style_is_used_by_the_planner(settings, now, tmp_path):
    from ftworthtv.examples import example_stories
    from ftworthtv.pipeline import run
    settings.brand["card"]["style"] = "quoted"
    settings.max_posts = 3
    report = run(settings, now=now, stories=example_stories(settings, now), publisher_name="dryrun")
    assert all(d.image and d.image.path.name == "quote.jpg" for d in report.drafts if d.story.source_kind != "culture")


def test_tweet_card_matches_the_reference_layout(settings, tmp_path):
    from ftworthtv.images.card import render_tweet_card
    photo = tmp_path / "p.jpg"
    Image.new("RGB", (1500, 1000), (60, 110, 60)).save(photo)
    out = render_tweet_card(name="Fort Worth Texas TV", handle="@FortWorthTexasTV", headline="New Texas leaders say THC rules are a top priority for 2027",
                            photo=photo, logo=settings.root / "assets" / "logo.png", out_path=tmp_path / "post.jpg", fonts_dir=settings.fonts_dir)
    with Image.open(out) as im:
        assert im.width == 1200 and 1.2 < im.width / im.height < 1.45     # landscape, like their screenshots (about 1.3:1)
        assert im.getpixel((5, 5)) == (255, 255, 255)                      # white card edge to edge
    tall = tmp_path / "tall.jpg"
    Image.new("RGB", (600, 900), (120, 60, 60)).save(tall)
    out2 = render_tweet_card(name="Fort Worth Texas TV", handle="@FortWorthTexasTV", headline="Fort Worth police searching for a sample person",
                             photo=tall, logo=None, out_path=tmp_path / "post2.jpg", fonts_dir=settings.fonts_dir, verified=True, credit="Photo: x")
    with Image.open(out2) as im:
        assert im.height <= int(1200 * 0.73 * 1.1) + 400                   # tall photo is contained, not stretched down the page
    out3 = render_tweet_card(name="Fort Worth Texas TV", handle="@FortWorthTexasTV", headline="Text-only post", photo=None, logo=None,
                             out_path=tmp_path / "post3.jpg", fonts_dir=settings.fonts_dir)
    assert out3.exists()


def test_default_style_is_our_post_card(settings, now, tmp_path):
    from ftworthtv.examples import example_stories
    from ftworthtv.pipeline import run
    settings.max_posts = 3
    report = run(settings, now=now, stories=example_stories(settings, now), publisher_name="dryrun")
    assert all(d.image and d.image.path.name == "post.jpg" for d in report.drafts)


def test_required_phrase_alternatives(settings):
    from ftworthtv.images.providers import PhotoCandidate, find_photo
    import ftworthtv.images.providers as prov
    cands = [PhotoCandidate(id="a", provider="wikimedia", url="u", source_url="https://commons.wikimedia.org/wiki/File:APHIS_inspection_San_Antonio_Zoo.jpg", credit="c", license="cc0", title="APHIS inspection at San Antonio Zoo"),
             PhotoCandidate(id="b", provider="wikimedia", url="u", source_url="https://commons.wikimedia.org/wiki/File:Hippopotamus_at_San_Antonio_Zoo.jpg", credit="c", license="cc0", title="Hippopotamus at San Antonio Zoo")]
    orig = prov._search_each
    try:
        prov._search_each = lambda *a, **k: iter([list(cands)])
        got = find_photo([("san antonio zoo", (), ("san antonio zoo", "hippo|hippopotamus"))], settings, fallback=False)
    finally:
        prov._search_each = orig
    assert got is not None and got.id == "b"


def test_commons_boilerplate_is_removed_from_credits_even_when_cut_short():
    from ftworthtv.images.library import clean_credit
    from ftworthtv.images.providers import _clean_artist
    assert _clean_artist("Billy Hathorn assumed (based on copyright c") == "Billy Hathorn"
    assert clean_credit("Photo: Billy Hathorn assumed (based on copyright c via Wikimedia Commons (CC BY-SA 3.0)") == "Photo: Billy Hathorn via Wikimedia Commons (CC BY-SA 3.0)"


def test_a_commons_graphic_or_poster_is_not_a_photo_of_the_subject():
    from ftworthtv.images.providers import _candidates_from_pages
    def page(pid, title, artist):
        return {"pageid": pid, "title": title, "imageinfo": [{"thumburl": f"https://upload.wikimedia.org/{pid}.jpg", "width": 2000, "height": 1300,
                "descriptionurl": "https://commons.wikimedia.org/x", "extmetadata": {"LicenseShortName": {"value": "CC BY-SA 4.0"}, "Artist": {"value": artist}}}]}
    payload = {"query": {"pages": [page(1, "File:260611-SDB-Graphic-_PTSD_Awareness_Month_(9744800).jpg", "Someone"),
                                   page(2, "File:Fort Worth VA clinic entrance.jpg", "U.S. Navy graphic by Petty Officer Emma Burgess"),
                                   page(3, "File:Fort Worth VA clinic entrance.jpg", "Jane Doe")]}}
    assert [c.id for c in _candidates_from_pages(payload)] == ["commons-3"]


def test_a_courtesy_rendering_on_the_outlets_page_is_not_its_own_photo(monkeypatch):
    from ftworthtv.images import third_party_photo
    from ftworthtv.models import Story
    import ftworthtv.sources.article as article
    calls = []
    def fake_fetch(url):
        calls.append(url)
        return {"caption": "A rendering of One University Place in Fort Worth. (Courtesy image | Goldenrod Cos.)", "credit": "image"}
    monkeypatch.setattr(article, "fetch_article", fake_fetch)
    s = Story(id="a", source="Fort Worth Report", source_kind="rss", title="One University Place breaks ground", summary="", url="https://fortworthreport.org/x",
              image_url="https://fortworthreport.org/r.jpg", image_policy="source_image")
    assert third_party_photo(s) and third_party_photo(s) and calls == ["https://fortworthreport.org/x"]   # read once, kept on the story
    monkeypatch.setattr(article, "fetch_article", lambda url: {"caption": "Volunteers sort cans at the Tarrant Area Food Bank. (Cristian ArguetaSoto | Fort Worth Report)", "credit": "Cristian ArguetaSoto"})
    own = Story(id="b", source="Fort Worth Report", source_kind="rss", title="Volunteers", summary="", url="https://fortworthreport.org/y",
                image_url="https://fortworthreport.org/v.jpg", image_policy="source_image")
    assert not third_party_photo(own)


def test_an_ap_archive_photo_on_the_outlets_page_is_a_wire_photo(monkeypatch):
    from ftworthtv.images import third_party_photo
    from ftworthtv.models import Story
    import ftworthtv.sources.article as article
    monkeypatch.setattr(article, "fetch_article", lambda url: {"caption": "A person pushes past a row of electric scooters on March 25, 2025. (Damian Dovarganes | AP archives)",
                                                                "credit": "Damian Dovarganes | AP archives"})
    s = Story(id="e", source="Fort Worth Report", source_kind="rss", title="Fort Worth eyes e-bike and electric scooter regulations", summary="",
              url="https://fortworthreport.org/e", image_url="https://fortworthreport.org/e.jpg", image_policy="source_image")
    assert third_party_photo(s)


def test_a_store_named_in_a_sponsor_line_is_never_the_picture():
    from ftworthtv.images.library import topics_for
    title = "Arlington teacher goes above and beyond to help students succeed after high school"
    body = (f"{title}. 52 Faces of Community is a Fort Worth Report weekly series spotlighting local unsung heroes. "
            "It is sponsored by Central Market, H-E-B and JPS Health Network.")
    assert "heb" not in topics_for(body, "community", "local", title=title)
    assert topics_for("H-E-B opens its first Fort Worth store downtown", "business", "local", title="H-E-B opens its first Fort Worth store downtown")[0] == "heb"


def test_a_screenshot_or_a_schedule_wallpaper_is_not_a_photo():
    """Render 106, Nov 21: 'Mavericks' found an OS X Mavericks Launchpad screenshot on Commons and 'Dallas Cowboys' a 2010
    Tony Romo schedule wallpaper on Flickr stamped 'photo property of the NFL'."""
    from ftworthtv.images.providers import PhotoCandidate, not_a_photo
    def cand(url, title=""):
        return PhotoCandidate(id="x", url=url, credit="", license="", provider="", source_url=url, width=2000, height=1200, alt=title, title=title)
    assert not_a_photo(cand("https://commons.wikimedia.org/wiki/File:OS_X_Mavericks%27_Launchpad.png", "OS X Mavericks' Launchpad"))
    assert not_a_photo(cand("https://www.flickr.com/photos/24887901@N04/4585039010", "Tony Romo 2010 Cowboys Schedule Wallpaper"))
    assert not_a_photo(cand("https://www.flickr.com/photos/1/2", "Dallas Cowboys logo"))
    assert not not_a_photo(cand("https://commons.wikimedia.org/wiki/File:Luka_Doncic_Dallas_Mavericks_2024.jpg", "Luka Doncic Dallas Mavericks 2024"))
    assert not not_a_photo(cand("https://commons.wikimedia.org/wiki/File:Fort_Worth_skyline_photographic_survey.jpg", "Fort Worth skyline"))


def test_an_i35w_photo_with_its_exit_signs_is_only_for_an_i35w_story(settings):
    """Render 115, Nov 22: an I-30 closure drew I-35W at the Ponder exit (FM 2449), signs readable."""
    from ftworthtv.images.library import pick
    i30 = pick(settings.root, ["highway"], used=set(), text="Eastbound I-30 will be closed from I-20 to Chapel Creek Boulevard.")
    assert i30 is None
    i35w = pick(settings.root, ["highway"], used=set(), text="Northbound I-35W lanes close at Basswood for construction.")
    assert i35w is not None and "i-35w" in i35w.id


def test_a_provider_that_times_out_is_not_asked_again_this_run(monkeypatch, settings):
    """Render 117, Nov 22: Openverse answered in minutes (four tries of 25 s per query) and the render hit its 15-minute
    limit with nothing pushed. A provider that times out once is skipped for the rest of the run."""
    import requests
    from ftworthtv.images import providers
    monkeypatch.setattr(providers, "_PROVIDERS_DOWN", set())
    monkeypatch.setattr(providers, "_search_started", [])
    calls = {"openverse": 0, "wikimedia": 0}
    def slow(query, settings=None, **kw):
        calls["openverse"] += 1
        raise requests.exceptions.ReadTimeout("Read timed out. (read timeout=15)")
    def commons(query, fresh=False):
        calls["wikimedia"] += 1
        return []
    monkeypatch.setattr(providers, "search_openverse", slow)
    monkeypatch.setattr(providers, "search_wikimedia", commons)
    monkeypatch.setattr(providers, "provider_order", lambda s: ["openverse", "wikimedia"])
    providers._search("Parade of Lights", settings)
    providers._search("Fall Family Day", settings)
    assert calls["openverse"] == 1 and calls["wikimedia"] == 2


def test_photo_searches_stop_when_the_run_budget_is_spent(monkeypatch, settings):
    import time
    from ftworthtv.images import providers
    monkeypatch.setattr(providers, "_PROVIDERS_DOWN", set())
    monkeypatch.setattr(providers, "_search_started", [time.monotonic() - providers.SEARCH_BUDGET_S - 1])
    monkeypatch.setattr(providers, "search_wikimedia", lambda q, fresh=False: (_ for _ in ()).throw(AssertionError("searched after the budget")))
    assert providers._search("fresh:Parade of Lights", settings) == []


def test_find_photo_moves_to_the_next_provider_when_none_will_do(settings, monkeypatch):
    """Nov 24, render 201: Openverse's 15 results for "U2" were graffiti walls, a spy plane and 2005-2009 concerts; the search
    stopped there while Commons had U2 on tour in 2018."""
    from ftworthtv.images import providers
    wall = providers.PhotoCandidate(id="openverse-1", url="https://x/a.jpg", credit="Photo: A", license="openverse-cc", provider="openverse",
                                    source_url="https://flickr.com/p/1", title="U2 360 Tour Barcelona 2009", taken="2009-07-02")
    tour = providers.PhotoCandidate(id="commons-1", url="https://x/b.jpg", credit="Photo: B", license="wikimedia-cc", provider="wikimedia",
                                    source_url="https://commons.wikimedia.org/wiki/File:U2_Paris_2018.jpg",
                                    title="U2 performing in Paris on Sept 8 2018 on Experience and Innocence Tour", taken="2018-09-08")
    calls = []
    monkeypatch.setattr(providers, "search_openverse", lambda q, s=None, **k: (calls.append("openverse"), [wall])[1])
    monkeypatch.setattr(providers, "search_wikimedia", lambda q, **k: (calls.append("wikimedia"), [tour])[1])
    monkeypatch.setattr(providers, "provider_order", lambda s: ["openverse", "wikimedia"])
    monkeypatch.setattr(providers, "_PROVIDERS_DOWN", set())
    monkeypatch.setattr(providers, "_search_started", [])
    got = providers.find_photo([("U2", (), ("u2",))], settings, fallback=False)
    assert got is not None and got.id == "commons-1" and calls == ["openverse", "wikimedia"]
    assert providers._search("U2", settings) == [wall]               # the first provider's results, as before


def test_a_species_record_is_not_a_character(settings, monkeypatch):
    """Nov 24, render 209: "Acacia cyclops 452574694.jpg" (seed pods) went on a story about the X-Men's Cyclops."""
    from ftworthtv.images import providers
    pods = providers.PhotoCandidate(id="commons-9", url="https://x/a.jpg", credit="c", license="wikimedia-cc", provider="wikimedia",
                                    source_url="https://commons.wikimedia.org/wiki/File:Acacia_cyclops_452574694.jpg", title="Acacia cyclops 452574694")
    monkeypatch.setattr(providers, "_search_each", lambda q, s: iter([[pods]]))
    assert providers.find_photo([("Cyclops", ("statue", "inaturalist"), ("cyclops",))], settings, fallback=False) is None
    assert providers.find_photo([("Cyclops", ("statue",), ("cyclops",))], settings, fallback=False) is pods   # a nature story keeps it


def test_liminal_space_and_ai_images_are_not_photos():
    """Nov 24, render 210: "Toys R Us Backrooms Level.jpg" for a Toys "R" Us opening in Fort Worth."""
    from ftworthtv.images.providers import PhotoCandidate, not_a_photo
    for name in ("Toys_R_Us_Backrooms_Level.jpg", "Liminal_mall_corridor.jpg", "AI-generated_storefront.png"):
        c = PhotoCandidate(id=name, url="u", credit="c", license="wikimedia-cc", provider="wikimedia",
                           source_url=f"https://commons.wikimedia.org/wiki/File:{name}", title=name.rsplit(".", 1)[0].replace("_", " "))
        assert not_a_photo(c), name
