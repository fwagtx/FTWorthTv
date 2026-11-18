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
