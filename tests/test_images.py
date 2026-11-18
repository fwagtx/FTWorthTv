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
