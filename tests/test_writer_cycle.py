"""Lessons from the first session-publishing cycles (Nov 19): what the template writer got wrong and must not again."""
from datetime import timedelta

from ftworthtv.models import Story
from ftworthtv.writer import _sentences, charge_phrase, template_copy

HILLWOOD = ("Strong demand drives continued development as Hillwood advances an industrial pipeline totaling 8.9 million square feet "
            "FORT WORTH, Texas (November 19, 2026) — Responding to sustained demand for Class A industrial space in North Texas, Hillwood "
            "today announced plans to develop two speculative industrial buildings totaling 354,593 square feet at AllianceTexas. "
            "Alliance Westport 41 (200,328 …")
DALLAS = ('The City of Dallas is investigating whether statistics showing a drop in violent crime may be inaccurate. Dallas is running an '
          'audit on potential errors in crime reporting. On Tuesday, Dallas City Auditor Rory Galter confirmed the city is investigating if '
          'crime statistics in the city may be inaccurate. "We are aware of possible incorrect reporting of crimes. This was identified in '
          'our entrance conference with the Dallas Police Department," the email read. Galter explained to city leaders on Tuesday that it '
          'is currently unknown how widespread the potential inaccuracies are.')


def test_all_caps_press_release_title_becomes_a_sentence_with_names_cased_from_the_text(settings, now):
    story = Story(id="h1", source="Fort Worth Business Press", source_kind="rss",
                  title="HILLWOOD EXPANDS ALLIANCETEXAS INDUSTRIAL PIPELINE WITH TWO NEW SPECULATIVE BUILDINGS", summary=HILLWOOD,
                  url="https://fortworthbusiness.com/x", published=now - timedelta(hours=1), category_hint="business", extra={"scope": "local"})
    copy = template_copy(story, settings, now)
    assert copy.headline == "Hillwood expands AllianceTexas industrial pipeline with two new speculative buildings"
    assert "TWO" not in copy.caption and "Alliancetexas" not in copy.caption


def test_a_caption_never_cuts_a_quote_in_half():
    sents = _sentences(DALLAS)
    assert sents and all(s.count('"') % 2 == 0 for s in sents)
    assert any("entrance conference" in s for s in sents)       # the quote is kept whole, not dropped


def test_wanted_charges_read_as_charges():
    assert charge_phrase("Aggravated Robbery") == "for aggravated robbery"
    assert charge_phrase("Failure to Comply, Sex Offender") == "on a sex offender failure-to-comply charge"
    assert charge_phrase("Aggravated Assault, Parole Violation") == "for aggravated assault and parole violation"


def test_a_newsrooms_donation_pitch_never_becomes_a_caption_sentence():
    text = ("Matt Krause, soon to be the only Republican on the county's commissioners court, called the midterm election a wake-up call "
            "for the party. The election is over, but the work of holding Texas officials accountable is just beginning. Help us pursue "
            "the truth. Every gift makes a difference. Matt Krause has spent his entire political career in conservative majorities.")
    sents = _sentences(text)
    assert sents and not any("accountable" in s or "gift" in s for s in sents)


def test_an_abbreviation_does_not_end_the_first_sentence():
    from ftworthtv.writer import _first_sentence
    assert _first_sentence("The 4-year-old students at Primrose School of N.E. Fort Worth collected 300 cans for Mission Arlington. More follows.") == \
        "The 4-year-old students at Primrose School of N.E. Fort Worth collected 300 cans for Mission Arlington."


def test_a_columnists_rhetoric_is_not_a_caption_sentence():
    text = ("It would be comforting if Republicans could tell themselves their state had been Californian, but that is not what the data show. "
            "You only search for moral victories when you lose. After the midterms, Republicans stumbled looking for one. "
            "What if the loss was not just a loss for Republicans? Texas added 2.1 million residents between 2020 and 2025, the census estimates.")
    sents = _sentences(text)
    assert "Texas added 2.1 million residents between 2020 and 2025, the census estimates." in sents
    assert not any(x.endswith("?") or "You " in x or x.startswith("It would be") for x in sents)


def test_a_photo_caption_is_never_a_caption_sentence():
    from ftworthtv.writer import _first_sentence
    text = ("Dallas Cowboys quarterback Dak Prescott (4) looks to pass against the Tennessee Titans during the fourth quarter at Nissan Stadium "
            "Thursday, Dec. 29, 2022, in Nashville, Tenn. The Cowboys travel to Nashville on Sunday with a new defensive play-caller, the team said Friday.")
    assert _sentences(text) == ["The Cowboys travel to Nashville on Sunday with a new defensive play-caller, the team said Friday."]
    assert _first_sentence(text) == ""                         # the lead is the figure caption: no sentence, not that one


def test_a_stations_teaser_line_is_not_a_caption_and_the_nut_graf_does_not_open_it():
    assert _sentences("Here are the latest updates from the KVUE Weather Impact Team.") == []
    text = ("The effort is being spearheaded by city council member Michael Crain, United Way of Tarrant County and Junior League of Fort Worth. "
            "Earlier this month, Fort Worth City Council member Michael Crain announced a citywide initiative to volunteer 500,000 hours as a community by April of next year.")
    sents = _sentences(text)
    assert sents[0].startswith("Earlier this month") and sents[1].startswith("The effort is being spearheaded")


def test_a_feed_item_with_nothing_to_say_is_skipped_not_posted_as_its_headline(settings, now):
    from ftworthtv.models import Story
    from ftworthtv.writer import write_copy
    settings.writer = "template"
    bare = Story(id="k", source="KXAN Austin", source_kind="rss", title="Beyond the pills: Texas veterans search for PTSD relief", summary="", url="https://x/k")
    copy, writer = write_copy(bare, settings, now)
    assert copy.skip and copy.skip_reason.startswith("no summary to post")
    told = Story(id="t", source="KXAN Austin", source_kind="rss", title="Beyond the pills: Texas veterans search for PTSD relief",
                 summary="Texas veterans are turning to therapy programs and service dogs as alternatives to medication, the station found.", url="https://x/t")
    copy, writer = write_copy(told, settings, now)
    assert not copy.skip


def test_an_imagn_dateline_caption_is_never_a_caption_sentence():
    from ftworthtv.writer import _first_sentence
    text = ("Nov 15, 2026; Arlington, Texas, USA; Dallas Cowboys defensive coordinator Christian Parker looks on from the sidelines during the game "
            "between the Cowboys and the 49ers at AT&T Stadium. Mandatory Credit: Jerome Miron-Imagn Images. "
            "Parker said Friday he was disappointed to lose play-calling duties but would keep his focus on the team.")
    assert _sentences(text) == ["Parker said Friday he was disappointed to lose play-calling duties but would keep his focus on the team."]
    assert _first_sentence(text) == ""


def test_an_editors_note_is_not_a_caption_sentence():
    text = ("Editor's note: The top Fort Worth news of the week includes sudden shutters and a grand holiday opening. "
            "Read on for our hottest headlines of the week, then plan some festive weekend fun here.")
    assert _sentences(text) == []


def test_a_residents_first_person_essay_is_not_a_caption():
    from ftworthtv.filters import column_label
    assert column_label("Where I Live: Ryanwood resident calls for more city support in east Fort Worth")
    text = ("I typically start my mornings either walking my dogs or running through my neighborhood, Ryanwood, and its Sunset Hills Park. "
            "My wife, Ashlynn, and I moved to this east Fort Worth neighborhood in September 2021. "
            "The city has promised more lighting for Sunset Hills Park by spring, a spokesperson said.")
    assert _sentences(text) == ["The city has promised more lighting for Sunset Hills Park by spring, a spokesperson said."]


def test_a_series_blurb_is_not_a_caption_sentence():
    text = ("William Thorburn's Fish for Life Foundation awards scholarships to help area students cover the cost of higher education. "
            "52 Faces of Community is a Fort Worth Report weekly series spotlighting local unsung heroes. "
            "It is sponsored by Central Market, H-E-B and JPS Health Network.")
    assert _sentences(text) == ["William Thorburn's Fish for Life Foundation awards scholarships to help area students cover the cost of higher education."]


def test_a_ledes_question_stays_when_the_next_sentence_refers_to_it():
    text = ("As more data centers come to Texas, who gets a say in how much water they use? "
            "Democrat Clayton Tucker made that question part of his winning campaign for Texas agriculture commissioner.")
    assert _sentences(text) == ["As more data centers come to Texas, who gets a say in how much water they use?",
                                "Democrat Clayton Tucker made that question part of his winning campaign for Texas agriculture commissioner."]
    alone = "Democrat Clayton Tucker made that question part of his winning campaign for Texas agriculture commissioner."
    assert _sentences(alone) == []                       # "that question" with no question before it is a cut
    rhetorical = "Have you ever wondered where your water comes from? The city council approved a new reservoir plan on Tuesday night."
    assert _sentences(rhetorical) == ["The city council approved a new reservoir plan on Tuesday night."]


def test_at_the_meeting_does_not_open_a_caption():
    text = ("At the meeting, the commission considered residential platting requirements, commercial property redevelopment and city-owned right-of-way. "
            "The Fort Worth City Plan Commission unanimously approved two waiver requests related to subdivisions.")
    sents = _sentences(text)
    assert sents[0].startswith("The Fort Worth City Plan Commission") and sents[1].startswith("At the meeting")


def test_a_meeting_recap_more_than_a_week_old_is_skipped(settings, now):
    from datetime import datetime, timezone
    from ftworthtv.models import Story
    from ftworthtv.writer import stale_meeting_recap, write_copy
    settings.writer = "template"
    old = Story(id="c", source="Fort Worth Report", source_kind="rss", title="Colleyville City Council considering pet resort permit", url="https://x/c",
                published=datetime(2026, 11, 22, 0, 20, tzinfo=timezone.utc),
                summary=("Editor's note: To learn more about how the transcript that informed this report was created, visit our site. "
                         "A proposed All American Pet Resorts on Colleyville Boulevard dominated the Nov. 4 Colleyville City Council meeting, "
                         "drawing hours of debate from residents, competing business owners, attorneys and council members."))
    assert stale_meeting_recap(old, now)
    copy, _ = write_copy(old, settings, now)
    assert copy.skip and copy.skip_reason == "a meeting recap more than a week old"
    fresh = Story(id="f", source="Fort Worth Report", source_kind="rss", title="Fort Worth council approves budget", url="https://x/f",
                  published=datetime(2026, 11, 22, 0, 20, tzinfo=timezone.utc),
                  summary="The Fort Worth City Council approved the budget at its Nov. 18 meeting after hours of debate, the city said.")
    upcoming = Story(id="u", source="Fort Worth Report", source_kind="rss", title="Council to vote on budget", url="https://x/u",
                     published=datetime(2026, 11, 22, 0, 20, tzinfo=timezone.utc),
                     summary="The Fort Worth City Council will take up the budget at its Dec. 2 meeting, the city said Friday.")
    assert not stale_meeting_recap(fresh, now) and not stale_meeting_recap(upcoming, now)


def test_a_nut_graf_about_programs_moves_and_a_repeated_figure_is_dropped():
    text = ("The city programs highlighted use $7 million of general and state funds to target homeless status among different demographics. "
            "The city outlined its current strategies in curbing homelessness during a Human Relations Commission meeting earlier this month. "
            "Highlighted initiatives include the Rapid Exit, High Impact and Flower Brewer Bridge programs. "
            "The city has $7 million in general and state funds to allow flexibility and piloting of innovative programs.")
    sents = _sentences(text)
    assert sents[0].startswith("The city outlined its current strategies")
    assert sum("$7 million" in s for s in sents) == 1


def test_a_cut_off_wire_recap_keeps_its_first_complete_clause(settings, now):
    """Nov 21: WFAA Sports' AP recaps (Mavericks 110-100, FC Dallas 3-0) came with 165-character teasers ending in "...";
    the article fetch was skipped as long enough and the writer found no sentence, so both went unposted."""
    from ftworthtv.models import Story
    from ftworthtv.writer import cut_off, salvage_lead, write_copy
    lead = ("Kyrie Irving scored 25 points and Cooper Flagg had 22 points, eight rebounds and six assists as the Dallas "
            "Mavericks used a late 11-0 run to beat the Los Angeles...")
    assert cut_off(lead) and not cut_off("The council voted 5-4.")
    assert salvage_lead(lead) == "Kyrie Irving scored 25 points and Cooper Flagg had 22 points."
    assert salvage_lead("Joaquín Valiente scored two second-half goals in a 2-minute span, Samuel Sarver added a stoppage-time "
                        "goal and FC Dallas beat the Portland Timbers 3-0 in Game 1...") == \
        "Joaquín Valiente scored two second-half goals in a 2-minute span."
    # a cut inside an appositive leaves a subject without its verb: nothing to salvage
    assert salvage_lead("Dak Prescott, who threw for 300 yards and three touchdowns, led the Cowboys past the Eagles 31-24 on...") == ""
    story = Story(id="mavs", source="WFAA Sports", source_kind="rss", category="sports", url="https://www.wfaa.com/article/syndication/x",
                  title="Kyrie Irving scores 25, Cooper Flagg 22 as the Mavericks top the Clippers 110-100", summary=lead, published=now)
    copy, _ = write_copy(story, settings, now, force_template=True)
    assert not copy.skip and "Cooper Flagg had 22 points." in copy.caption


def test_a_cut_off_news_lead_is_not_trimmed_into_a_different_story(settings, now):
    from ftworthtv.models import Story
    from ftworthtv.writer import write_copy
    story = Story(id="fire", source="WFAA", source_kind="rss", category="breaking", url="https://www.wfaa.com/article/news/x",
                  title="Crews contain apartment fire in east Fort Worth",
                  summary="The fire at the apartment complex on East Lancaster Avenue was contained within an hour, but two firefighters were taken to...",
                  published=now)
    copy, _ = write_copy(story, settings, now, force_template=True)
    assert copy.skip and "only a headline" in copy.skip_reason      # never "The fire ... was contained within an hour." alone
