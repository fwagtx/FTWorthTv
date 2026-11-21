from datetime import datetime, timezone

from ftworthtv.checks import caption_problems, preflight, source_text, wanted_still_listed
from ftworthtv.models import PostCopy, PostDraft, Story


def _story(**kw):
    base = dict(id="s1", source="Fort Worth Report", source_kind="rss", title="Trinity Metro cuts On-Demand zones",
                summary="Trinity Metro's board approved changes Monday to the On-Demand service. The subsidized rides cost about $28 each, "
                        "Tara Crawford said. Paul David Williams, 70, said he will walk two blocks from the Walmart at 717 W. Berry St.",
                url="https://example.com/story")
    base.update(kw)
    return Story(**base)


def _copy(caption):
    return PostCopy(headline="h", caption=caption, first_comment="Source", category="traffic")


def test_grounded_caption_passes():
    cap = "Trinity Metro's board approved changes Monday to the On-Demand service. The subsidized rides cost about $28 each, Crawford said."
    assert caption_problems(_copy(cap), _story()) == []


def test_invented_number_quote_and_sentence_fail():
    s = _story()
    assert any("number" in p for p in caption_problems(_copy("The rides cost about $45 each."), s))
    assert any("quotation" in p for p in caption_problems(_copy("Williams said, 'I will never ride the bus again in my life.'"), s))
    assert any("sentence" in p for p in caption_problems(_copy("The governor announced a statewide pension overhaul for teachers yesterday."), s))


def test_structured_fields_count_as_source():
    s = _story(source_kind="wanted", summary="", title="WANTED: John Doe",
               extra={"name": "John Doe", "charge": "Aggravated Robbery", "reward": "$2,000", "tip_phone": "817-469-TIPS (8477)"})
    cap = "Fort Worth police are looking for John Doe, wanted for aggravated robbery. Crime Stoppers is offering up to $2,000. Call 817-469-TIPS (8477)."
    assert caption_problems(_copy(cap), s, writer="template") == []
    assert any("number" in p for p in caption_problems(_copy(cap.replace("$2,000", "$5,000")), s, writer="template"))
    assert "aggravated robbery" in source_text(s)


def test_wanted_recheck(monkeypatch):
    from ftworthtv import http

    class R:
        def __init__(self, text):
            self.text = text

    class S:
        def __init__(self, text):
            self.text = text

        def get(self, url, timeout=20, allow_redirects=True):
            return R(self.text)

    s = _story(source_kind="wanted", extra={"name": "John Doe"}, url="https://police.example.gov/most-wanted")
    monkeypatch.setattr(http, "session", lambda: S("<h3>John Doe</h3> Aggravated Robbery"))
    assert wanted_still_listed(s) is None
    monkeypatch.setattr(http, "session", lambda: S("<h3>Someone Else</h3>"))
    assert "no longer listed" in wanted_still_listed(s)


def test_preflight_offline_only_checks_text():
    d = PostDraft(story=_story(), copy=_copy("The subsidized rides cost about $28 each, Crawford said."), writer="template", mode="link", link="https://example.com/story")
    assert preflight(d, network=False) == []


def test_parse_article_picks_the_story_block_not_the_teaser():
    from ftworthtv.sources.article import parse_article
    html = ('<html><head><meta property="og:title" content="Cooper Flagg scores 33 as Mavs beat Warriors">'
            '<meta property="og:description" content="Cooper Flagg scored a career-high 33 points on Wednesday night."></head><body>'
            '<article><p>Anthropic said the offering consists of 980 million shares and signals investor enthusiasm for AI stocks.</p></article>'
            '<article><p>Cooper Flagg scored a career-high 33 points on Wednesday night as the Mavericks beat the Warriors 118-104.</p>'
            '<p>Golden State has not won since Stephen Curry was injured earlier this month.</p></article></body></html>')
    info = parse_article(html, "https://example.com/story")
    assert info["summary"].startswith("Cooper Flagg scored a career-high 33 points")
    assert "Anthropic" not in info["summary"]


def test_parse_article_leaves_the_figure_caption_out_of_the_summary():
    from ftworthtv.sources.article import parse_article
    html = ('<html><head><meta property="og:title" content="Cowboys face Titans"><meta property="og:description" content="A preview."></head><body><article>'
            '<figure><img src="/p.jpg"><p class="caption">Dallas Cowboys quarterback Dak Prescott (4) looks to pass against the Tennessee Titans at Nissan Stadium Thursday, Dec. 29, 2022, in Nashville, Tenn.</p></figure>'
            '<aside><p>Related: the five biggest questions facing the Cowboys defense this week.</p></aside>'
            '<p>The Cowboys travel to Nashville on Sunday with a new defensive play-caller and fading playoff hopes, a week after the loss.</p>'
            '</article></body></html>')
    info = parse_article(html, "https://example.com/story")
    assert "Nissan Stadium" not in info["summary"] and "Related" not in info["summary"]
    assert info["summary"].startswith("The Cowboys travel to Nashville") and info["image"].endswith("/p.jpg")


def test_parse_article_hands_back_the_first_figure_caption():
    from ftworthtv.sources.article import parse_article
    html = ('<html><head><meta property="og:title" content="T"></head><body><article><figure><img src="/r.jpg">'
            '<figcaption>A rendering of One University Place. (Courtesy image | Goldenrod Cos.)</figcaption></figure>'
            '<p>One University Place broke ground on Nov. 19, the second project from Goldenrod Cos. in Fort Worth.</p></article></body></html>')
    info = parse_article(html, "https://example.com/s")
    assert info["caption"].startswith("A rendering of One University Place") and "Courtesy" in info["caption"]


def test_parse_article_leaves_a_caption_block_out_of_the_summary():
    from ftworthtv.sources.article import parse_article
    html = ('<html><head><meta property="og:title" content="T"></head><body><article>'
            '<div class="image-caption"><p>Nov 15, 2026; Arlington, Texas, USA; Dallas Cowboys defensive coordinator Christian Parker looks on from the sidelines.</p></div>'
            '<p>Parker said Friday he was disappointed to lose play-calling duties but would keep his focus on the team, which hosts the Eagles on Sunday.</p>'
            '</article></body></html>')
    info = parse_article(html, "https://example.com/s")
    assert info["summary"].startswith("Parker said Friday") and "sidelines" not in info["summary"]


def test_parse_article_takes_the_block_that_shares_the_title_not_the_longest(monkeypatch):
    from ftworthtv.models import Story
    from ftworthtv.sources import article
    from ftworthtv.sources.article import enrich_summary, parse_article
    other = "<p>" + " ".join(["Bad news for the wet bandits, it looks like Kevin McCallister is back in a new Home Alone sequel with Macaulay Culkin, NBC News confirmed."] * 3) + "</p>"
    html = ('<html><head><meta property="og:title" content="Dallas Cowboys fan dies after altercation during 49ers game: Arlington Police"></head><body>'
            f'<article>{other}</article>'
            '<article><p>A Dallas Cowboys fan died after an altercation in the stands during the game against the 49ers, Arlington police said Saturday.</p></article>'
            '</body></html>')
    info = parse_article(html, "https://example.com/s")
    assert info["summary"].startswith("A Dallas Cowboys fan died") and "Home Alone" not in info["summary"]
    monkeypatch.setattr(article, "fetch_article", lambda url: {"title": "Dallas Cowboys fan dies after altercation during 49ers game: Arlington Police",
                                                                "description": "", "summary": "Bad news for the wet bandits, Kevin McCallister is back in a new Home Alone sequel, NBC News confirmed."})
    s = Story(id="f", source="NBC 5 DFW", source_kind="rss", title="Dallas Cowboys fan dies after altercation during 49ers game: Arlington Police", summary="", url="https://x/f")
    enrich_summary(s)
    assert "Home Alone" not in (s.summary or "")                       # another article's body never becomes the story's summary


def test_a_captions_byline_tail_is_the_credit():
    from ftworthtv.sources.article import photo_credit
    html = '<figure><img src="/p.jpg"><figcaption>Attorney General Ken Paxton speaks during a campaign rally in Tyler on Feb. 16, 2026. Michael Cavazos for The Texas Tribune</figcaption></figure>'
    assert photo_credit(html, {}) == "Michael Cavazos for The Texas Tribune"
    html2 = '<figure><figcaption>Volunteers sort cans at the Tarrant Area Food Bank. (Cristian ArguetaSoto | Fort Worth Report)</figcaption></figure>'
    assert photo_credit(html2, {}).startswith("Cristian ArguetaSoto")
