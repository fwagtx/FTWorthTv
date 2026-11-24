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


def test_the_lead_limit_never_ends_a_sentence_on_a_middle_initial():
    """Render 115, Nov 22: the Arlington pastor caption ended 'After a four-day trial before U.S. District Judge Mark T.'"""
    from ftworthtv.writer import _sentences
    summary = ("A jury found an Arlington pastor guilty on conspiracy and wire fraud charges in a real estate and investment scheme. "
               "Sentencing is March 4, 2027. A federal jury found an Arlington pastor guilty of orchestrating a real estate and "
               "investment fraud scheme that impacted more than 70 victims in the United States, Colombia, Mexico, and the Dominican "
               "Republic, according to the U.S. Attorney's Office. After a four-day trial before U.S. District Judge Mark T. Pittman, "
               "the jury found 53-year-old Richard Reinaldo Garcia, a pastor at several churches in Arlington, guilty on Thursday of "
               "one count of conspiracy to commit wire fraud and three counts of wire fraud.")
    out = _sentences(summary)
    assert out and not any(s.endswith(" T.") for s in out)


CBS_TCU_SUMMARY = ("The move came a day after a 38-17 loss to No. 2 Utah in its home finale. Updated on: November 22, 2026 / 12:51 PM CST / "
                   "CBS/AP CBS Sports Texas has independently confirmed that Texas Christian University fired head football coach Sonny Dykes, "
                   "four years after Dykes led the Horned Frogs to a CFP championship game in his first season in Fort Worth. The Horned Frogs "
                   "were just 5-6 a day after a 38-17 loss to No. 2 Utah in its home finale. The Frogs' five losses before that had all been "
                   "one-score games against Power Four opponents, and by a combined 25 points. The Frogs were coming off back-to-back 9-4 "
                   "seasons when Dykes got a multi-year extension in April.")


def test_cbs_update_stamp_and_attribution_do_not_cost_the_lead():
    """Nov 22, render 122: the CBS lead ('...has independently confirmed that TCU fired Sonny Dykes') was 221 characters with
    its attribution and an 'Updated on:' stamp glued on, so it was dropped and the caption opened 'The Frogs' five losses
    before that...'."""
    from ftworthtv.writer import _sentences
    sents = _sentences(CBS_TCU_SUMMARY)
    assert sents[0].startswith("Texas Christian University fired head football coach Sonny Dykes")
    assert not any("Updated on" in s or "CBS/AP" in s or "has independently confirmed" in s for s in sents)
    assert "before that" not in sents[0]


def test_a_dangling_back_reference_never_opens_the_caption():
    from ftworthtv.writer import _sentences
    sents = _sentences("The Frogs' five losses before that had all been one-score games against Power Four opponents. "
                       "The Frogs were coming off back-to-back 9-4 seasons when Dykes got a multi-year extension in April.")
    assert sents[0].startswith("The Frogs were coming off")


def test_archive_replays_are_dropped_and_live_watch_posts_are_not():
    from ftworthtv.filters import archive_replay
    assert archive_replay("Watch the breaking news, coverage of President JFK's assassination in Dallas as it happened in 1963")
    assert archive_replay("From the archives: Fort Worth's 1971 Stockyards fire")
    assert not archive_replay("WATCH: Fort Worth police chase ends in crash on I-35W")
    assert not archive_replay("Watch party for TCU-Texas Tech set for Sundance Square")


def test_an_arrest_on_a_traffic_stop_is_crime_not_traffic():
    from ftworthtv.filters import infer_category
    from ftworthtv.models import Story
    def cat(title):
        return infer_category(Story(id="x", title=title, url="u", source="FOX 4", source_kind="rss", summary=""))
    assert cat("North Texas traffic stop leads to arrest of armed man accused of soliciting 15-year-old on Snapchat") == "crime"
    assert cat("City solicits bids for new Northside library") != "crime"
    assert cat("Runner in cardiac arrest saved by off-duty nurses at Cowtown Marathon") != "crime"


def test_firing_a_coach_is_an_event_and_apps_are_never_photo_subjects():
    from ftworthtv.images.subject import entities, happened
    assert happened("TCU fires Sonny Dykes four years after making CFP championship game")
    assert happened("Cowboys part ways with defensive coordinator")
    assert happened("Rangers dismiss hitting coach after losing season")
    assert not happened("TCU coach Sonny Dykes talks bowl hopes before Texas Tech")
    names = entities("North Texas traffic stop leads to arrest of armed man accused of soliciting 15-year-old on Snapchat")
    assert not any("snapchat" in n.lower() for n in names)


def test_a_text_date_on_commons_cannot_pass_a_date_bar(settings, monkeypatch):
    """Nov 22, render 123: Commons gave DateTimeOriginal as 'July 11, 2016', which sorted after '2026-11-08' letter by
    letter, so a 2016 photo of Sonny Dykes in a Cal polo went on 'TCU fires Sonny Dykes'."""
    from ftworthtv.images import providers
    old = providers.PhotoCandidate(id="commons-50477992", url="https://x/a.jpg", credit="Photo: A", license="wikimedia-cc",
                                   provider="wikimedia", source_url="https://commons.wikimedia.org/wiki/File:Sonny_Dykes_at_2016_Bay_Area_College_Football_Media_Day.jpg",
                                   title="Sonny Dykes at 2016 Bay Area College Football Media Day", taken="July 11, 2016")
    undated_name = providers.PhotoCandidate(id="commons-2", url="https://x/b.jpg", credit="Photo: B", license="wikimedia-cc",
                                            provider="wikimedia", source_url="https://commons.wikimedia.org/wiki/File:Sonny_Dykes_2019.jpg",
                                            title="Sonny Dykes 2019", taken="2026-11-20")
    fresh = providers.PhotoCandidate(id="commons-3", url="https://x/c.jpg", credit="Photo: C", license="wikimedia-cc",
                                     provider="wikimedia", source_url="https://commons.wikimedia.org/wiki/File:Sonny_Dykes_TCU_Utah.jpg",
                                     title="Sonny Dykes TCU Utah", taken="21 November 2026")
    monkeypatch.setattr(providers, "_search", lambda q, s: [old, undated_name])
    assert providers.find_photo("fresh:Sonny Dykes", settings, fallback=False, taken_after="2026-11-08") is None
    monkeypatch.setattr(providers, "_search", lambda q, s: [old, undated_name, fresh])
    assert providers.find_photo("fresh:Sonny Dykes", settings, fallback=False, taken_after="2026-11-08").id == "commons-3"
    assert providers.iso_date("July 11, 2016") == "2016-07-11" and providers.iso_date("2016:07:11 14:22:05") == "2016-07-11"
    assert providers.iso_date("unknown") == ""


def test_national_rankings_lists_are_dropped_unless_a_local_team_is_named():
    from ftworthtv.filters import rankings_list
    assert rankings_list("Coaches Poll top 25: Texas, Tennessee climb; UCLA, Indiana tumble in college football rankings")
    assert rankings_list("NFL Power Rankings Week 12: Chiefs climb")
    assert not rankings_list("TCU falls out of AP Top 25 after loss to Utah")
    assert not rankings_list("Cowboys climb in NFL power rankings after win over Eagles")


def test_a_name_that_starts_with_a_number_keeps_it():
    """Nov 22, render 124: "'Holiday in the Park' kicks off at Six Flags Over Texas" searched for "Flags Over Texas"."""
    from ftworthtv.images.subject import entities
    assert "Six Flags Over Texas" in entities("'Holiday in the Park' kicks off at Six Flags Over Texas with new lights")
    assert "Fort Worth" in " ".join(entities("Two Fort Worth men charged in Northside robbery"))
    assert not any(n.lower().startswith("two ") for n in entities("Two Fort Worth men charged in Northside robbery"))


def test_a_schools_change_in_leadership_release_is_the_firing_already_posted():
    """Nov 22: TCU Athletics' 'TCU Football Announces Change in Leadership' came an hour after 'TCU fires Sonny Dykes'."""
    from ftworthtv.filters import same_personnel_news
    posted = "TCU fires Sonny Dykes four years after making CFP championship game"
    lead = ("TCU Director of Intercollegiate Athletics Mike Buddie announced Sunday that head football coach Sonny Dykes "
            "has been relieved of his duties.")
    assert same_personnel_news("TCU Football Announces Change in Leadership", lead, posted)
    assert not same_personnel_news("TCU Football Announces Change in Leadership", "", posted)          # nothing to tie it yet
    assert not same_personnel_news("TCU names Jim Smith interim coach after firing Sonny Dykes", lead, posted)   # a hire is news
    assert not same_personnel_news("TCU Football Announces Change in Leadership", lead, "Sonny Dykes talks bowl hopes")


def test_a_word_capitalised_by_a_colon_is_not_a_subject_and_mid_headline_names_keep_their_adjective():
    """Nov 22, render 126: "Made in Tarrant: Gobble up barbecue at Big Bear's Smokehouse" searched for "Gobble" (a turkey
    photo could have passed) and for "Bear Smokehouse"."""
    from ftworthtv.images.subject import entities, plan_subject
    t = "Made in Tarrant: Gobble up barbecue at Big Bear’s Smokehouse"
    names = entities(t, "Big Bear’s Smokehouse in Haltom City smokes turkeys.")
    assert "Gobble" not in names and "Big Bear Smokehouse" in names
    assert plan_subject(t, "Big Bear’s Smokehouse in Haltom City smokes turkeys.", "food").primary != "Gobble"
    assert not any(n.lower().startswith("big") for n in entities("Big crash closes lanes on I-35W in north Fort Worth"))


def test_a_highlight_clip_page_is_skipped_and_clip_sentences_never_reach_a_caption(settings):
    """Nov 22, render 127: CBS Sports' 'Titans' Carnell Tate stuns Cowboys ...' opened 'Watch Titans rookie Carnell Tate
    score a wild 59-yard touchdown ...' (a clip we cannot show) and had 'the Tennessee Titans , stripping'."""
    from datetime import datetime, timezone
    from ftworthtv.models import Story
    from ftworthtv.writer import _sentences, write_copy
    summary = ("Watch Titans rookie Carnell Tate score a wild 59-yard touchdown after the Cowboys failed to touch him down during "
               "Sunday's game. The Dallas Cowboys made a change on defense ahead of their matchup with the Tennessee Titans , "
               "stripping defensive coordinator Christian Parker of play-calling duties and handing them to Mike Pettine.")
    story = Story(id="t", title="Titans' Carnell Tate stuns Cowboys with one of NFL season's strangest touchdowns", url="u",
                  source="CBS Sports", source_kind="rss", summary=summary, category="sports")
    copy, _ = write_copy(story, settings, datetime(2026, 11, 22, 20, 44, tzinfo=timezone.utc), force_template=True)
    assert copy.skip and "clip" in copy.skip_reason
    sents = _sentences("The Cowboys won 30-17. Check out the play here: Prescott to Lamb for 40 yards on third down. "
                       "Dallas moved to 7-4 with the win over the Tennessee Titans , their third straight.")
    assert not any(s.lower().startswith("check out") for s in sents)
    assert any("Tennessee Titans, their third straight" in s for s in sents)
    assert not _sentences("Watch out for ice on bridges tonight across Tarrant County, officials said.") == []   # "watch out" is advice


def test_caricatures_and_opinion_art_are_not_photos():
    """Nov 22, render 128: 'Medicare' found DonkeyHotey's 'Dr. Oz Is In Charge of Your Medicare and Medicaid. You Better
    Watch Out!' (captioned 'Medicare for All Sucks, Go Trumpcare!') for a Medicare counseling story."""
    from ftworthtv.images.providers import PhotoCandidate, not_a_photo
    oz = PhotoCandidate(id="commons-1", url="u", credit="Photo: DonkeyHotey via Wikimedia Commons (CC BY-SA 2.0)", license="wikimedia-cc",
                        provider="wikimedia", source_url="https://commons.wikimedia.org/wiki/File:Dr._Oz_Is_In_Charge_of_Your_Medicare_and_Medicaid._You_Better_Watch_Out!.jpg",
                        title="Dr. Oz Is In Charge of Your Medicare and Medicaid. You Better Watch Out!")
    assert not_a_photo(oz)
    cartoon = PhotoCandidate(id="commons-2", url="u", credit="Photo: A via Wikimedia Commons", license="wikimedia-cc", provider="wikimedia",
                             source_url="https://commons.wikimedia.org/wiki/File:Medicare_editorial_cartoon.jpg", title="Medicare editorial cartoon")
    assert not_a_photo(cartoon)
    card = PhotoCandidate(id="commons-3", url="u", credit="Photo: B via Wikimedia Commons", license="wikimedia-cc", provider="wikimedia",
                          source_url="https://commons.wikimedia.org/wiki/File:Tarrant_County_Courthouse_2019.jpg", title="Tarrant County Courthouse 2019")
    assert not not_a_photo(card)


def test_press_releases_are_dropped_and_a_bar_foundation_is_not_food():
    """Nov 22, render 128: FW Business Press reprinted 'TCYLA is pleased to announce that it has been awarded a grant from
    the Texas Bar Foundation', filed as food because of 'Bar'."""
    from ftworthtv.filters import infer_category, press_release
    from ftworthtv.models import Story
    title = ("Tarrant County Young Lawyers Association Receives Grant from Texas Bar Foundation for Legal Information Clinic for "
             "Local Social Workers")
    summary = ("The Tarrant County Young Lawyers Association (TCYLA) is pleased to announce that it has been awarded a grant from the "
               "Texas Bar Foundation to support a Legal Information Clinic for Social Workers.")
    assert press_release(title, summary)
    assert not press_release("Fort Worth council approves new library", "The council voted 9-0 on Tuesday.")
    assert infer_category(Story(id="x", title=title, url="u", source="FWBP", source_kind="rss", summary=summary)) != "food"


def test_a_caricaturists_work_is_not_a_photo_whatever_its_file_name():
    from ftworthtv.images.providers import PhotoCandidate, not_a_photo
    plain = PhotoCandidate(id="commons-4", url="u", credit="Photo: DonkeyHotey via Wikimedia Commons (CC BY 2.0)", license="wikimedia-cc",
                           provider="wikimedia", source_url="https://commons.wikimedia.org/wiki/File:Mehmet_Oz.jpg", title="Mehmet Oz")
    assert not_a_photo(plain)


def test_a_demonstrative_opener_needs_the_sentence_before_it():
    """Nov 22, render 129: 'That involves the West Fork and Parker County public utility agencies.' followed a sentence
    that was dropped for length, so 'that' pointed at nothing in the caption."""
    from ftworthtv.writer import _sentences
    long = ("The water district is engaging in conversations with officials from regional planning groups consisting of counties "
            "and municipalities across Wise and Parker counties, chief engineering officer Rachel Ickert shared with board directors Tuesday.")
    text = ("The Tarrant Regional Water District's service area could expand as communities west of the county grow. " + long +
            " That involves the West Fork and Parker County public utility agencies. While yet to be officially established, "
            "13 municipalities have expressed interest in joining the Parker County regional utility, a commissioner said.")
    sents = _sentences(text)
    assert not any(s.startswith("That involves") for s in sents)
    kept = _sentences("Fort Worth will close two pools next summer for repairs. That means families will have to drive farther to swim.")
    assert any(s.startswith("That means") for s in kept)


def test_a_house_fire_is_breaking_news_and_takes_a_picture_of_the_fire_or_none():
    """Nov 22, render 131: WFAA's 'Fort Worth firefighters battle large 2-story house fire' was filed as 'other' and got a
    library photo of a parked Fort Worth Fire rescue truck, a stand-in for a fire that happened."""
    from ftworthtv.filters import infer_category
    from ftworthtv.images.subject import happened
    from ftworthtv.models import Story
    t = "Fort Worth firefighters battle large 2-story house fire"
    st = Story(id="x", title=t, url="u", source="WFAA", source_kind="rss",
               summary="Photos of the fire showed flames coming up through the roof of the home. Officials say no injuries were reported.")
    assert infer_category(st) == "breaking"
    assert happened(t)
    assert happened("Apartment fire displaces 12 families in east Fort Worth")
    assert not happened("Fort Worth Fire Department hiring new recruits for spring academy")


def test_in_game_score_updates_are_dropped_but_a_halftime_show_is_not():
    """Nov 22: 'Dominant Cowboys offense shines as they lead Titans 27-9 at halftime' was deferred by the sports cap to the
    next morning, when the game was long over."""
    from ftworthtv.filters import in_game_update
    assert in_game_update("Dominant Cowboys offense shines as they lead Titans 27-9 at halftime")
    assert in_game_update("Rangers lead Astros 4-1 after the third inning")
    assert in_game_update("Cowboys vs. Titans live updates: score, highlights")
    assert not in_game_update("Cowboys dominate Titans 51-30 as Dak Prescott accounts for 5 TDs")
    assert not in_game_update("Post Malone to headline Cowboys Thanksgiving halftime show")


def test_two_fort_worth_events_are_not_the_same_game():
    """Nov 22, render 132: same_game read 'Fort' and 'Worth' as two team names, so NBC 5's '2 minors killed, 3 others
    seriously injured after van crashes and catches fire in Fort Worth' and WFAA's house fire were dropped as the same
    story as a morning shooting post."""
    from ftworthtv.filters import same_game
    shooting = "1 man is dead after being shot following a fight in Fort Worth"
    assert not same_game("2 minors killed, 3 others seriously injured after van crashes and catches fire in Fort Worth", shooting)
    assert not same_game("Fort Worth firefighters battle large 2-story house fire", shooting)
    assert same_game("Arch Manning steps up as Longhorns blow out Arkansas", "No. 5 Texas avoids letdown, routs Arkansas 45-3")
    assert same_game("Cowboys dominate Titans 51-30 as Dak Prescott accounts for 5 TDs", "Prescott, Cowboys rout Titans 51-30")


def test_north_texas_news_is_not_a_unt_game():
    from ftworthtv.filters import same_game
    assert not same_game("North Texas man killed in Dallas crash", "North Texas woman shot in Dallas, police say")


def test_a_fire_or_gunfire_is_not_a_firing_and_a_city_is_not_a_person():
    """Nov 22, render 134: NBC 5's van crash ('... catches fire in Fort Worth') was dropped as the same news as 'Fort Worth
    firefighters battle large 2-story house fire': 'fire' read as a firing and 'Fort Worth' as a person."""
    from ftworthtv.filters import same_personnel_news as same
    assert not same("2 minors killed, 3 others seriously injured after van crashes and catches fire in Fort Worth", "",
                    "Fort Worth firefighters battle large 2-story house fire")
    assert not same("Police: shots fired at officer during chase", "Officer Jane Doe was not hurt.",
                    "Arlington fires police officer Jane Doe after investigation")
    lead = ("TCU Director of Intercollegiate Athletics Mike Buddie announced Sunday that head football coach Sonny Dykes "
            "has been relieved of his duties.")
    assert same("TCU Football Announces Change in Leadership", lead, "TCU fires Sonny Dykes four years after making CFP championship game")


def test_a_scorigami_story_is_the_game_already_posted_and_roundups_are_columns():
    """Nov 22, render 137: 'Cowboys vs. Titans ends in historic scorigami after late Tennessee touchdown' waited for the next
    day under the sports cap although the 51-30 final had gone out, and CBS's 'NFL Week 11 winners and losers' waited too."""
    from ftworthtv.filters import roundup_column, same_game
    assert same_game("Cowboys vs. Titans ends in historic scorigami after late Tennessee touchdown",
                     "Cowboys dominate Titans 51-30 as Dak Prescott accounts for 5 TDs")
    assert roundup_column("NFL Week 11 winners and losers: Cowboys offense makes history in get-right win, Steelers stumble")
    assert roundup_column("3 takeaways from the Cowboys' 51-30 win over the Titans")
    assert not roundup_column("Cowboys dominate Titans 51-30 as Dak Prescott accounts for 5 TDs")


def test_ends_in_alone_does_not_make_a_crime_story_a_game():
    from ftworthtv.filters import _sports_result, same_game
    assert not _sports_result("East Fort Worth altercation ends in deadly shooting, police say")
    assert not same_game("East Fort Worth altercation ends in deadly shooting, police say", "Arlington standoff ends in arrest after 4 hours")
    assert same_game("Cowboys vs. Titans ends in historic scorigami after late Tennessee touchdown",
                     "Cowboys dominate Titans 51-30 as Dak Prescott accounts for 5 TDs")


def test_a_grades_column_is_a_column():
    from ftworthtv.filters import roundup_column
    assert roundup_column("NFL Week 11 grades for every team: Cowboys earn 'A-' for high-flying win, Steelers nearly fail")
    from ftworthtv.filters import game_notes
    assert not roundup_column("Fort Worth ISD grades: TEA releases A-F ratings for district schools")
    assert not game_notes("Fort Worth ISD grades: TEA releases A-F ratings for district schools")
    assert not game_notes("Texas releases school report cards; see how Tarrant County districts did")
    assert game_notes("Cowboys vs. Titans grades: Dak Prescott earns an A in a 51-30 rout")


def test_a_bare_cbs_date_stamp_is_stripped():
    """Nov 22, render 143: 'November 22, 2026 / 7:52 PM CST / CBS Texas A high-speed incident on Highway 360 ...'."""
    from ftworthtv.writer import _sentences
    text = ("A high-speed incident on Highway 360 in Arlington ends in a fiery crash, sending one driver to the hospital on Sunday. "
            "November 22, 2026 / 7:52 PM CST / CBS Texas The Arlington Police Department said officers were conducting speed "
            "enforcement along Hwy. 360 around 3:30 p.m. when they clocked a Chevrolet Malibu.")
    sents = _sentences(text)
    assert not any("CST" in s or "CBS Texas" in s for s in sents)
    assert any(s.startswith("The Arlington Police Department said") for s in sents)


def test_a_price_drop_or_a_grant_win_is_not_a_game_that_happened():
    """Nov 22, render 144: 'Gas prices drop ahead of Thanksgiving, but fewer Texans are hitting the road' counted as an
    event ('drop' is a game result word, and 'Texans' read as the NFL team), so no topic photo could be used."""
    from ftworthtv.images.subject import happened
    assert not happened("Gas prices drop ahead of Thanksgiving, but fewer Texans are hitting the road")
    assert not happened("Fort Worth wins $5 million grant for trails")
    assert not happened("Texas tops list of states with most new residents")
    assert happened("TCU Falls to Utah in Home Finale")
    assert happened("Cowboys drop to 5-6 after loss in Philadelphia")
    assert happened("Texans beat Colts 24-17")


def test_routine_postgame_pressers_are_not_news():
    from ftworthtv.filters import routine_presser
    assert routine_presser("Jerry Jones: Postgame #TENvsDAL | Dallas Cowboys 2026")
    assert routine_presser("Dak Prescott: Postgame Week 11 #TENvsDAL")
    assert not routine_presser("Fort Worth police chief press conference on Sunday shooting")   # news, not routine
    assert routine_presser("Mike McCarthy press conference: Cowboys coach on the Titans game")
    assert not routine_presser("Watch: Fort Worth Zoo welcomes baby giraffe")


def test_a_gas_price_story_gets_a_gas_photo_or_none_and_thanksgiving_as_a_date_is_not_a_subject():
    """Nov 22, render 144: 'Gas prices drop ahead of Thanksgiving ...' would have fallen to the Thanksgiving turkey or the
    Capitol: the library has no gas photo, and 'ahead of Thanksgiving' is when, not what."""
    from ftworthtv.images.library import topic_excluded, topics_for
    t = "Gas prices drop ahead of Thanksgiving, but fewer Texans are hitting the road"
    assert topics_for(t.lower(), "business", "texas", title=t) == ["gas"]
    assert topic_excluded("thanksgiving", t)
    assert not topic_excluded("thanksgiving", "Food bank hands out turkey dinners ahead of Thanksgiving")
    assert "thanksgiving" in topics_for("thanksgiving dinner served to 500 at fort worth shelter", "community", "local",
                                        title="Thanksgiving dinner served to 500 at Fort Worth shelter")


def test_a_gas_price_story_searches_for_a_gas_station_not_a_dinner_table():
    """Nov 22, render 146: the gas story's beat search was 'Thanksgiving dinner table' and found a Flickr photo of
    strangers at a family table."""
    from ftworthtv.models import Story
    from ftworthtv.writer import topic_image_query
    st = Story(id="g", title="Gas prices drop ahead of Thanksgiving, but fewer Texans are hitting the road", url="u", source="KXAN",
               source_kind="rss", summary="Gas prices are falling fast ahead of Thanksgiving, but AAA expects fewer Texans on the road.")
    assert topic_image_query(st, "Fort Worth skyline") == "gasoline pump nozzle fueling car"
    st2 = Story(id="h", title="Food bank hands out 2,000 Thanksgiving turkeys in east Fort Worth", url="u", source="FWR",
                source_kind="rss", summary="Volunteers handed out turkeys and sides ahead of Thanksgiving.")
    assert "turkey" in topic_image_query(st2, "Fort Worth skyline")


def test_team_highlight_reels_are_not_news():
    from ftworthtv.filters import highlight_reel
    assert highlight_reel("George Pickens' Best Plays from 102-yard game | Week 11 Highlights")
    assert highlight_reel("Javonte Williams' Best plays from 2-TD game vs. Titans | Week 11 Highlights")
    assert not highlight_reel("Fort Worth police release video of Sunday chase on I-35W")


def test_a_holiday_light_show_takes_a_picture_of_the_lights_or_none():
    """Nov 23, render 150: 'Christmas in the Garden returns to Fort Worth Botanic Garden' came with the garden's arbors on a
    sunny October day in 2019."""
    from ftworthtv.images.subject import LIGHT_WORDS, light_show, plan_subject, provider_queries
    t = "Christmas in the Garden returns to Fort Worth Botanic Garden"
    body = "Christmas in the Garden returns to the Fort Worth Botanic Garden with the Winter Cathedral and new light installations."
    plan = plan_subject(t, body, "culture")
    assert plan.entity_topics == []
    for (query, _avoid, words), _label in provider_queries(plan, t, "culture"):
        assert LIGHT_WORDS in words
    assert light_show("GM Financial Parade of Lights returns to Fort Worth for the 2026 holiday season")
    assert not light_show("Fort Worth Botanic Garden opens new rose garden")


def test_a_photo_credit_is_the_photographer_not_the_town_before_the_name():
    """Nov 23, render 151: a Texas Tribune caption ending '... in Lago Vista Sergio Flores for The Texas Tribune' was
    credited to 'Lago Vista Sergio Flores'."""
    from ftworthtv.sources.article import photo_credit
    html = ("<figure><img src='a.jpg'><figcaption>Students walk the halls between classes at Lago Vista High School in "
            "Lago Vista Sergio Flores for The Texas Tribune</figcaption></figure>")
    assert photo_credit(html, {}) == "Sergio Flores for The Texas Tribune"
    html2 = "<figure><figcaption>(Cristian ArguetaSoto | Fort Worth Report)</figcaption></figure>"
    assert "Cristian ArguetaSoto" in photo_credit(html2, {})


def test_one_forecast_per_outlet_per_morning():
    """Nov 23, render 151: WFAA's 'Chilly temperatures to start the week, here's your Thanksgiving forecast' was drafted
    25 minutes after WFAA's 'Possible Frost and Freeze for North Texas This Week' went out."""
    from datetime import datetime, timedelta, timezone
    from ftworthtv.models import Story
    from ftworthtv.pipeline import _same_outlet_forecast
    from ftworthtv.state import State
    now = datetime(2026, 11, 23, 12, 44, tzinfo=timezone.utc)
    state = State.__new__(State)
    state.data = {"posted": {"a": {"at": (now - timedelta(minutes=30)).isoformat(), "category": "weather", "source": "WFAA",
                                   "title": "Possible Frost and Freeze for North Texas This Week"}}}
    wfaa = Story(id="b", title="DFW Weather: Chilly temperatures to start the week", url="u", source="WFAA", source_kind="video", summary="")
    nbc = Story(id="c", title="NBC 5 Forecast: cold front arrives", url="u", source="NBC 5 DFW", source_kind="rss", summary="")
    assert _same_outlet_forecast(state, wfaa, now)
    assert not _same_outlet_forecast(state, nbc, now)
    assert not _same_outlet_forecast(state, wfaa, now + timedelta(hours=13))


def test_render_152_rules():
    """Nov 23, render 152: a Dallas street dedication, 'Photo: Photo: Andreas Praefcke', and WFAA's Salvation Army video the
    morning after the Cowboys-Salvation Army post."""
    from ftworthtv.filters import other_city_civic, same_subjects
    from ftworthtv.images.providers import _clean_artist
    assert other_city_civic("Fair Park streets dedicated in honor of 2 leaders from African American Museum in Dallas")
    assert not other_city_civic("Fort Worth renames Northside park for longtime community leader")
    assert _clean_artist("Photo: Andreas Praefcke") == "Andreas Praefcke"
    assert _clean_artist("Photograph by Jane Doe") == "Jane Doe"
    video = ("Salvation Army kicks off Thanksgiving campaign at AT&T Stadium. The nonprofit is celebrating decades of "
             "partnership with the Cowboys.")
    assert same_subjects(video, "Dallas Cowboys mark 30 years of giving back with Salvation Army")
    assert not same_subjects(video, "Cowboys dominate Titans 51-30 as Dak Prescott accounts for 5 TDs")


def test_render_153_rules():
    """Nov 23, render 153: a Texas Tribune explainer whose caption ended 'Here's what their plans could mean for taxpayers.',
    an hour after another Tribune agenda piece; and KXAN's 'SEC Championship Game scenarios: How Texas can join Georgia'."""
    from ftworthtv.filters import hypothetical_sports
    from ftworthtv.pipeline import _source_posts_on
    from ftworthtv.state import State
    from ftworthtv.writer import _sentences
    sents = _sentences("Texas Democrats are considering cutting property taxes and ending corporate subsidies. Here’s what their "
                       "plans could mean for taxpayers. Texas Republican lawmakers spent years and billions of dollars trying to "
                       "rein in the state’s property taxes.")
    assert not any(s.lower().startswith("here") for s in sents) and len(sents) == 2
    state = State.__new__(State)
    state.data = {"posted": {"a": {"source": "The Texas Tribune", "at": "2026-11-23T07:37:00-06:00"},
                             "b": {"source": "WFAA", "at": "2026-11-23T06:47:00-06:00"}}}
    assert _source_posts_on(state, "The Texas Tribune", "2026-11-23") == 1
    assert _source_posts_on(state, "The Texas Tribune", "2026-11-24") == 0
    assert hypothetical_sports("SEC Championship Game scenarios: How Texas can join Georgia in Atlanta")
    assert hypothetical_sports("What needs to happen for TCU to become bowl eligible")
    assert not hypothetical_sports("TCU fires Sonny Dykes four years after making CFP championship game")


def test_render_154_rules():
    """Nov 23, render 154: ESPN's Rockets feature with the Toyota Center and an 'Original uploader was ...' credit; NBC 5's
    Bedford crash ('The crash happened overnight') the morning after FOX 4 reported the same crash."""
    from datetime import datetime, timezone
    from ftworthtv.filters import other_metro_team
    from ftworthtv.images.providers import _clean_artist
    from ftworthtv.models import Story
    from ftworthtv.pipeline import _stale_relative_time
    from ftworthtv.state import State
    assert _clean_artist("Original uploader was Hequalstohenry of en.wikipedia") == "Hequalstohenry"
    assert other_metro_team("How a season without their 'admiral' showed the Rockets what they were missing")
    assert not other_metro_team("Mavericks beat Rockets 112-104 behind Flagg's 31")
    state = State.__new__(State)
    state.data = {"deferred": {"x": {"at": "2026-11-22T17:44:51+00:00", "reason": "daily cap for crime reached",
                                     "title": "Bedford police arrest suspected intoxicated driver after chase ends in crash into local business"}}}
    st = Story(id="n", title="Driver arrested after car crashes into Bedford business following pursuit", url="u", source="NBC 5 DFW",
               source_kind="rss", summary="", published=datetime(2026, 11, 23, 8, 11, tzinfo=timezone.utc))
    now = datetime(2026, 11, 23, 14, 20, tzinfo=timezone.utc)
    assert _stale_relative_time(state, st, "A driver is under arrest. The crash happened overnight in the 2700 block of Brown Trail.", now)
    assert not _stale_relative_time(state, st, "A driver is under arrest after a crash on Brown Trail.", now)


def test_render_156_rules():
    """Nov 23, render 156: NBC 5's feed put a sentence from further down the story ahead of its lede; Fort Worth Weekly
    carried a gambling-stream advertorial; Billboard's GTA VI soundtrack cover story drafted as the national post."""
    from ftworthtv.filters import gambling_advertorial, national_feature
    from ftworthtv.writer import _sentences
    nbc = ("Detectives learned that the shooting victim and suspect were involved in a verbal and physical altercation when the "
           "suspect shot the victim at least one time. Fort Worth police are investigating a homicide that left a man dead and "
           "another arrested after an altercation on Saturday. Officers were dispatched to a shooting near the 600 block of The "
           "Heights Dr. and found a man with a gunshot wound to his torso. Officials said he was pronounced dead at the scene. "
           "Detectives learned that the shooting victim and suspect were involved in a verbal and physical altercation when the "
           "suspect shot the victim at least one time. Police said that the shooting suspect contacted 911 for medical assistance.")
    out = _sentences(nbc)
    assert out[0].startswith("Fort Worth police are investigating a homicide")
    assert sum(s.startswith("Detectives learned") for s in out) <= 1
    # an excerpt followed by the full text starts at the full text, in order
    excerpt = ("The city council approved the new budget on Tuesday night. The plan adds twelve officers to the patrol division. "
               "The vote was seven to two. The city council approved the new budget on Tuesday night. The plan adds twelve "
               "officers to the patrol division. The vote was seven to two. Two members said the plan spends too much on overtime.")
    out = _sentences(excerpt)
    assert out[0].startswith("The city council approved") and out[1].startswith("The plan adds")
    fww = ("Game Show Sets Have Found a Second Life on Interactive Live Streams",
           "The wheel slows beneath a flapper. Anyone who grew up watching game shows knows the rhythm. Some streams let adults wager on the action.")
    assert gambling_advertorial(*fww)
    assert not gambling_advertorial("Texas lawmakers weigh casino gambling bill", "The Texas House will debate whether to allow casinos.")
    assert not gambling_advertorial("Cowboys' fourth-down gamble pays off in win over Eagles")
    assert national_feature("‘It’s Not Just a Song on the Radio’: How Music Became A Main Character In ‘Grand Theft Auto VI’",
                            "https://www.billboard.com/music/features/gta-6-radio-songs-soundtrack-justice-billboard-cover-1236386805/")
    assert national_feature("Robbing Banks is a Blast, But I Wish There Were More Houses to Repair in GTA 6")
    assert not national_feature("GTA VI is finally here: Rockstar's long-awaited sequel launches")
    assert not national_feature("How to watch the Cowboys Thanksgiving game")


def test_render_157_rules(settings, now):
    """Nov 23, render 157: KENS 5's feed brought back its Nov 2023 story on a Fort Worth CEO and two children killed the night
    before Thanksgiving with a new date; Billboard's list of CMA new-artist winners found a Volvo XC40 for "CMA"."""
    from datetime import datetime, timedelta, timezone
    from ftworthtv.filters import filter_stories, holiday_not_yet, national_feature
    from ftworthtv.images.subject import plan_subject, provider_queries
    from ftworthtv.models import Story
    from ftworthtv.state import State
    nov23 = datetime(2026, 11, 23, 15, 23, tzinfo=timezone.utc)                      # Thanksgiving 2026 is Nov 26
    assert holiday_not_yet("Crash report details how Fort Worth CEO, two children were killed the night before Thanksgiving", "", nov23)
    assert holiday_not_yet("Three killed in Thanksgiving Day crash", "", nov23)
    assert not holiday_not_yet("Two killed in crash days before Thanksgiving on I-35W", "", nov23)   # true today
    assert not holiday_not_yet("Man killed while hanging Christmas lights in Keller", "", nov23)    # the lights are not a date
    assert not holiday_not_yet("A year after Thanksgiving crash killed Fort Worth CEO, family remembers", "", nov23)
    assert not holiday_not_yet("Thanksgiving Day forecast: dry and cold, but a dead calm wind", "", nov23)
    assert not holiday_not_yet("Cowboys vs. Chiefs on Thanksgiving Day: Prescott shot down rumors of injury", "", nov23)
    assert not holiday_not_yet("Man killed in crash on Christmas Eve", "", datetime(2026, 12, 25, 3, tzinfo=timezone.utc))
    kens = Story(id="kens", source="KENS 5 San Antonio", source_kind="rss",
                 title="Crash report details how Fort Worth CEO, two children were killed the night before Thanksgiving",
                 summary="Zach Muckleroy, the CEO of Muckleroy & Falls construction company in Fort Worth, and his children died in the crash.",
                 url="https://www.kens5.com/article/news/local/x", published=now - timedelta(hours=1))
    kept, dropped = filter_stories([kens], settings, State(settings.state_path), now)
    assert not kept and "old story" in dropped[0][1]
    assert national_feature("All CMA Awards New Artist of the Year Winners Over 30: Stephen Wilson Jr., Jelly Roll & More",
                            "https://www.billboard.com/lists/cma-awards-new-artist-of-the-year-winners-over-age-30/")
    title = "All CMA Awards New Artist of the Year Winners Over 30: Stephen Wilson Jr., Jelly Roll & More"
    plan = plan_subject(title, "The CMA has presented new artist of the year 46 times.", "culture")
    queries = provider_queries(plan, title, "culture")
    assert queries and all(len(q[2]) == 2 and "awards" in q[2][1].split("|") for q, _ in queries)   # "cma" alone never decides
    bare = plan_subject("CMA is back", "", "culture")
    assert bare.search_names == ["CMA"]
    assert not [q for q, label in provider_queries(bare, "CMA is back", "culture") if label == "entity:cma"]


def test_render_158_rules(settings, now):
    """Nov 23, render 158: Fort Worth Weekly's "Simple Ways To Enjoy The End Of A North Texas Summer" (late September, weeks
    of triple digits) dated the week of Thanksgiving."""
    from datetime import datetime, timedelta, timezone
    from ftworthtv.filters import filter_stories, out_of_season
    from ftworthtv.models import Story
    from ftworthtv.state import State
    nov = datetime(2026, 11, 23, 16, tzinfo=timezone.utc)
    summary = ("There is a specific moment every year, usually somewhere in late September, when you step outside in Fort Worth "
               "and realize the air has finally let go. Until then, there are still several weeks of triple digits to negotiate.")
    assert out_of_season("Simple Ways To Enjoy The End Of A North Texas Summer", summary, nov)
    assert not out_of_season("Simple Ways To Enjoy The End Of A North Texas Summer", summary, datetime(2026, 8, 20, tzinfo=timezone.utc))
    assert not out_of_season("Fort Worth ISD summer school changes approved", "The board approved changes.", nov)
    assert not out_of_season("Fort Worth recorded 50 triple-digit days this year", "", nov)
    fww = Story(id="fww", source="Fort Worth Weekly", source_kind="rss", title="Simple Ways To Enjoy The End Of A North Texas Summer",
                summary=summary, url="https://www.fwweekly.com/x", published=now - timedelta(hours=1), always_relevant=True)
    kept, dropped = filter_stories([fww], settings, State(settings.state_path), now)
    assert not kept and "season" in dropped[0][1]


def test_render_159_rules():
    """Nov 23, render 159: Variety's "Justin Timberlake Documentary Trailer: Apple TV Series to Unpack Britney Spears, Janet
    Jackson Controversies" went out of the render with a Fort Worth Stockyards beat photo. The planner was handed
    story.text(), which is lowercased, so every word of a Title Case headline looked like a common word and the names were
    lost; the publish-time check read the same lowercased text and agreed. Both now read the summary as written."""
    from pathlib import Path
    from ftworthtv.checks import photo_subject_problem
    from ftworthtv.images.subject import plan_subject
    from ftworthtv.models import ImageAsset, PostCopy, PostDraft, Story
    title = "Justin Timberlake Documentary Trailer: Apple TV Series to Unpack Britney Spears, Janet Jackson Controversies"
    summary = ("The trailer for Apple TV's upcoming Justin Timberlake documentary teases details about his controversies around "
               "Britney Spears and Janet Jackson. Apple TV has confirmed that it will launch a new four-part documentary.")
    story = Story(id="jt", source="Variety", source_kind="rss", title=title, summary=summary, url="https://variety.com/x")
    plan = plan_subject(title, summary, "culture")
    assert plan.primary == "Justin Timberlake" and plan.mode == "search"
    assert plan_subject(title, story.text(), "culture").mode != "beat"       # even a lowercased text keeps a named subject
    draft = PostDraft(story=story, copy=PostCopy(headline=title, caption=summary, category="culture"), writer="template",
                      image=ImageAsset(path=Path("post.jpg"), credit="Photo: x", license="openverse-cc", provider="openverse",
                                       subject="beat:Fort Worth Stockyards"))
    assert photo_subject_problem(draft) and "Justin Timberlake" in photo_subject_problem(draft)


def test_render_160_rules():
    """Nov 23, render 160: The Hollywood Reporter's page gave "Logo text Justin Timberlake is the subject of ..." and an ad
    script ("blogherads.adq.push(function () { ...") inside the article text."""
    from ftworthtv.writer import _sentences
    thr = ('A "raw, reflective and revealing portrait" of Timberlake is coming to Apple TV. Logo text Justin Timberlake is the '
           'subject of a new four-part documentary series that promises to explore his personal and professional life. '
           "blogherads.adq.push(function () { blogherads .defineSlot( 'medrec', 'gpt-article-mid-article-uid0' ) .setTargeting( 'pos', 'mid' ) });")
    out = _sentences(thr)
    assert out[1].startswith("Justin Timberlake is the subject")
    assert not any("Logo text" in s or "blogherads" in s for s in out)


def test_render_160_broken_feed_descriptions():
    """Nov 23, render 160: NBC 5's feed carried one Sunday Night Football article under every item's <description>, so
    "Christmas in the Garden returns to Fort Worth Botanic Garden" and nine other items were filed as sports news (and sports
    may go out as a text card). A description that is not about its headline, or that repeats under several headlines, is
    dropped for the item's own excerpt or the article."""
    from datetime import datetime, timezone
    from ftworthtv.filters import infer_category
    from ftworthtv.sources.rss import parse_feed
    snf = ("<p>Sunday Night Football is heading to Cleveland for the first time in seven years, as the Browns will host the Las Vegas "
           "Raiders in primetime. The Browns are in the thick of the AFC wild card race; quarterback Deshaun Watson threw a touchdown.</p>")
    feed = f"""<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>NBC 5</title>
<item><title>Christmas in the Garden returns to Fort Worth Botanic Garden</title><link>https://www.nbcdfw.com/news/local/garden/1/</link>
<excerpt><![CDATA[Christmas in the Garden brings 22 light installations to the Fort Worth Botanic Garden.]]></excerpt>
<description><![CDATA[{snf}]]></description></item>
<item><title>Parade of Lights returns to downtown Fort Worth</title><link>https://www.nbcdfw.com/news/local/parade/2/</link>
<excerpt><![CDATA[The 44th annual Parade of Lights returns with more than 100 floats.]]></excerpt>
<description><![CDATA[{snf}]]></description></item>
<item><title>Browns host Raiders on Sunday Night Football</title><link>https://www.nbcdfw.com/news/sports/snf/3/</link>
<description><![CDATA[The Browns host the Raiders in primetime as quarterback Deshaun Watson faces his former team.]]></description></item>
</channel></rss>"""
    stories = {s.title: s for s in parse_feed({"name": "NBC 5 DFW"}, feed, datetime.now(timezone.utc))}
    garden = stories["Christmas in the Garden returns to Fort Worth Botanic Garden"]
    assert "Sunday Night Football" not in garden.summary and "light installations" in garden.summary
    assert infer_category(garden) != "sports"
    assert infer_category(stories["Parade of Lights returns to downtown Fort Worth"]) != "sports"
    assert "Deshaun Watson" in stories["Browns host Raiders on Sunday Night Football"].summary      # a real description stays


def test_render_161_rules(settings):
    """Nov 23, render 161: NWS's Freeze Warning for Tarrant and 20 other counties said only "until 9:00 AM" (the freeze is
    Tuesday night into Wednesday) under an empty radar map; CBS Texas's Cowboys blood drive caption opened "Texas It's the
    season of giving" and said "next week" for a drive held that day."""
    from datetime import datetime, timezone
    from ftworthtv.images.subject import radar_fits
    from ftworthtv.writer import _UPDATED_RE, alert_area, alert_when, restate_relative_day
    monday = datetime(2026, 11, 23, 18, 0, tzinfo=timezone.utc)
    summary = ("Freeze Warning issued November 23 at 11:24AM CST until November 25 at 9:00AM CST by NWS Fort Worth TX. * WHAT..."
               "Sub-freezing temperatures as low as 27 expected. * WHERE...Areas along and west of a line from Gainesville to Fort "
               "Worth. * WHEN...From 11 PM Tuesday to 9 AM CST Wednesday. * IMPACTS...Frost and freeze conditions could kill crops.")
    assert alert_when(summary, "2026-11-25T09:00:00-06:00", monday, settings.tz) == " from 11 PM Tuesday to 9 AM Wednesday"
    assert alert_when("", "2026-11-25T09:00:00-06:00", monday, settings.tz) == " until 9:00 AM Wednesday"
    assert alert_when("", "2026-11-24T09:00:00-06:00", monday, settings.tz) == " until 9:00 AM tomorrow"
    assert alert_when("", "2026-11-23T21:00:00-06:00", monday, settings.tz) == " until 9:00 PM"
    area = "Montague; Cooke; Young; Jack; Wise; Denton; Stephens; Palo Pinto; Parker; Tarrant; Eastland"
    assert alert_area(area, short=True) == "Tarrant and 10 other North Texas counties"
    assert alert_area("Tarrant; Johnson") == "Tarrant and Johnson counties"
    assert alert_area("Tarrant") == "Tarrant County" and alert_area("Tarrant, TX") == "Tarrant, TX"
    assert not radar_fits("Freeze Warning") and not radar_fits("Heat Advisory") and not radar_fits("Wind Advisory")
    assert radar_fits("Severe Thunderstorm Warning") and radar_fits("Winter Weather Advisory") and radar_fits("Flash Flood Warning")
    cbs = "Updated on: November 23, 2026 / 11:23 AM CST / CBS Texas It's the season of giving."
    assert _UPDATED_RE.sub("", cbs) == "It's the season of giving."
    caption = "The Cowboys are teaming with Carter BloodCare to hold a blood drive at AT&T Stadium in Arlington next week."
    text = "The event, scheduled for Monday, Nov. 23, from 10 a.m. to 6 p.m., will feature Cowboys legends."
    assert restate_relative_day(caption, text, monday, settings.tz).endswith("in Arlington today.")
    assert restate_relative_day(caption, "The event is scheduled for Monday, Nov. 30.", monday, settings.tz) == caption


def test_render_162_rules():
    """Nov 23, render 162: the Freeze Warning (frost, lows near 27) drew the library's only "ice" photo, the February 2021
    Dallas-Fort Worth snowstorm. A dry freeze takes frost (or gray skies), never snow; an ice storm is not a thunderstorm."""
    from ftworthtv.images.subject import subject_fits, weather_topics
    from ftworthtv.writer import alert_image_query
    title = "Freeze Warning: Montague; Cooke; Parker; Tarrant; Johnson"
    body = "Sub-freezing temperatures as low as 27 expected. Frost and freeze conditions could kill crops."
    assert weather_topics(f"{title} {body}")[0] == "frost" and "ice" not in weather_topics(f"{title} {body}")
    assert weather_topics("Ice Storm Warning for Tarrant County")[0] == "ice"
    assert weather_topics("Winter Storm Warning: heavy snow")[0] == "ice"
    assert weather_topics("Severe Thunderstorm Warning")[0] == "storm"
    assert subject_fits(title, body, "weather", "beat:ice", kind="nws_alert")[0] is False
    assert subject_fits(title, body, "weather", "beat:frost", kind="nws_alert")[0] is True
    assert subject_fits(title, body, "weather", "beat:skyline", kind="nws_alert")[0] is True
    assert alert_image_query("Freeze Warning") == "frost on grass"
    assert alert_image_query("Winter Storm Warning") == "snow ice road Texas"


def test_render_164_rules():
    """Nov 23, render 164: NBC 5's Texas Tech result was held as "this statewide outlet already had its post today" because
    NBC 5's local shooting, schedule and parade posts counted. Only an outlet's statewide or national posts count."""
    from ftworthtv.pipeline import _source_posts_on
    from ftworthtv.state import State
    state = State.__new__(State)
    state.data = {"posted": {
        "a": {"source": "NBC 5 DFW", "at": "2026-11-23T09:55:00-06:00", "scope": "local"},
        "b": {"source": "NBC 5 DFW", "at": "2026-11-23T10:58:00-06:00", "scope": "local"},
        "c": {"source": "The Texas Tribune", "at": "2026-11-23T07:37:00-06:00", "scope": "texas"},
        "d": {"source": "KXAN Austin", "at": "2026-11-23T08:00:00-06:00"},                 # recorded before scopes: counts
    }}
    assert _source_posts_on(state, "NBC 5 DFW", "2026-11-23") == 0
    assert _source_posts_on(state, "The Texas Tribune", "2026-11-23") == 1
    assert _source_posts_on(state, "KXAN Austin", "2026-11-23") == 1


def test_render_165_rules():
    """Nov 23, render 165: FOX 4's "Northbound Dallas North Tollway to close overnight at Northwest Highway" drafted as a
    text card, and Variety's "Super Bowl 2027 and Jay-Z Halftime Show to Screen in Imax Theaters" ("Worry not, because Imax
    is bringing Super Bowl LXI to the big screen") drafted as a sports text card."""
    from ftworthtv.filters import another_citys_traffic
    from ftworthtv.pipeline import _national_result
    assert another_citys_traffic("Northbound Dallas North Tollway to close overnight at Northwest Highway")
    assert not another_citys_traffic("I-30 eastbound closed overnight near Cooper Street in Arlington")
    assert not another_citys_traffic("SH 360 lanes close for bridge work")
    assert not another_citys_traffic("Crash shuts down westbound I-20 in Grand Prairie")
    assert not _national_result("Super Bowl 2027 and Jay-Z Halftime Show to Screen in Imax Theaters")
    assert _national_result("Chiefs beat Eagles to win Super Bowl LXI")


def test_render_166_rules(settings, now):
    """Nov 23, render 166: MLB.com's "Miller won't return as Astros' pitching coach in '27 (source)" read as "other" (the
    Astros feed had no sports hint and no sports word matched), so the other-metro team rule let it through with the
    Astros' ballpark as its picture."""
    from datetime import timedelta
    from ftworthtv.filters import filter_stories, infer_category
    from ftworthtv.models import Story
    from ftworthtv.state import State
    astros = Story(id="hou", source="Houston Astros (MLB.com)", source_kind="rss", title="Miller won't return as Astros' pitching coach in '27 (source)",
                   summary="A longtime fixture on the Astros' coaching staff will not be back next season under new manager Brad Ausmus.",
                   url="https://www.mlb.com/news/x", published=now - timedelta(hours=1))
    assert infer_category(astros) == "sports"
    kept, dropped = filter_stories([astros], settings, State(settings.state_path), now)
    assert not kept and "another metro" in dropped[0][1]
    assert any(src.get("name") == "Houston Astros (MLB.com)" and src.get("category_hint") == "sports" for src in settings.sources.get("rss", []))
    texans = Story(id="tx", source="KXAN Austin", source_kind="rss", title="Texans vote on 17 constitutional amendments", summary="Voters across Texas decide.", url="u")
    assert infer_category(texans) != "sports"


def test_render_168_rules():
    """Nov 23 (a Monday), render 168: NBC 5's "No. 11 Texas Tech moves closer to another Big 12 title game with win at
    Baylor" ("after Tech's 20-10 win over Baylor on Saturday") drew Jones AT&T Stadium from 2013 for a game played at
    Baylor, and "TCU interim HC Andy Avalos introduced ahead of regular-season finale against TTU" drew an empty Amon G.
    Carter Stadium."""
    from datetime import datetime
    from zoneinfo import ZoneInfo
    from ftworthtv.filters import stale_result
    from ftworthtv.images.subject import happened
    assert happened("No. 11 Texas Tech moves closer to another Big 12 title game with win at Baylor")
    assert happened("TCU interim HC Andy Avalos introduced ahead of regular-season finale against TTU")
    assert happened("Fort Worth hires new police chief")
    assert not happened("Fort Worth introduces new recycling carts")
    assert not happened("City council introduced a budget amendment")
    monday = datetime(2026, 11, 23, 14, 0, tzinfo=ZoneInfo("America/Chicago"))
    tech = "coach Joey McGuire said after Tech's 20-10 win over Baylor on Saturday."
    assert stale_result("No. 11 Texas Tech moves closer to another Big 12 title game with win at Baylor", tech, monday)
    assert not stale_result("Cowboys beat Eagles", "The Cowboys beat the Eagles 30-20 on Sunday.", monday)
    assert not stale_result("TCU preview", "TCU visits Texas Tech on Thursday after a loss to Utah.", monday)
    assert stale_result("Mavericks recap", "Saturday's 110-100 win over the Clippers put Dallas at .500.", monday)


def test_render_169_rules():
    """Nov 23, render 169: KXAN's "$850,000 Texas Two Step jackpot set to expire" searched the game's name and found a
    firefly (an iNaturalist record of the Texas Two-step Flasher); IGN's "Family-Friendly Fortnite Streamer Goes Viral After
    Picking Up GTA 6" passed as a national moment with a Monster Jam x Fortnite truck."""
    from ftworthtv.filters import national_feature
    from ftworthtv.images.subject import plan_subject, provider_queries
    plan = plan_subject("$850,000 Texas Two Step jackpot set to expire", "A Texas Two Step ticket worth $850,000 remains unclaimed.", "other")
    assert plan.mode == "entity" and plan.entity_topics == ["lottery"]
    title = "Mavericks guard signs extension with Dallas"
    queries = provider_queries(plan_subject(title, "The Dallas Mavericks signed their guard to a new deal on Monday.", "sports"), title, "sports",
                               people_allowed=True)
    assert queries and all("inaturalist" in q[1] for q, _ in queries)       # a species record is never a picture of a person or a team
    bird = "Rare whooping crane spotted at Fort Worth Nature Center"
    assert all("inaturalist" not in q[1] for q, _ in provider_queries(plan_subject(bird, "", "community"), bird, "community"))
    assert national_feature("Family-Friendly Fortnite Streamer Goes Viral After Picking Up GTA 6 And Performing the Ultimate Heelturn")


def test_render_170_rules():
    """Nov 23, render 170: Billboard's "Taylor Swift Shares the Sweetest Moment With Her Niece After Travis Kelce Scores Epic
    Touchdown" drafted as a national sports text card: the result sat in the "after" clause of a celebrity item."""
    from ftworthtv.pipeline import _national_result
    assert not _national_result("Taylor Swift Shares the Sweetest Moment With Her Niece After Travis Kelce Scores Epic Touchdown")
    assert _national_result("Chiefs beat Eagles to win Super Bowl LXI")
    assert _national_result("Cowboys roll past Eagles after Prescott throws three touchdowns")


def test_render_172_rules():
    """Nov 23, render 172: ESPN's "Texas A&M names Thornton interim athletic director, effective Dec. 1" drew Kyle Field:
    a name between "names" and the role hid the job change from the happening rule."""
    from ftworthtv.images.subject import happened
    assert happened("Texas A&M names Thornton interim athletic director, effective Dec. 1")
    assert happened("Keller ISD board names lone finalist for superintendent")
    assert not happened("Fort Worth names new park after longtime council member")


def test_render_174_rules():
    """Nov 23, render 174: the Fort Worth Report's Keller ISD bond story ended '..."a bond is critical to that work," Wilson
    said.' after the sentence naming Superintendent Cory Wilson was cut: a bare surname is no one to a reader."""
    from ftworthtv.writer import introduce_speakers
    text = ("Keller ISD Superintendent Cory Wilson said the district needs a bond. “There’s a lot of work that needs to take place "
            "within the school district, and a bond is critical to that work,” Wilson said.")
    cap = "Keller ISD could ask voters again in May.\n\n“There’s a lot of work,” Wilson said."
    assert introduce_speakers(cap, text).endswith("“There’s a lot of work,” Superintendent Cory Wilson said.")
    already = "Superintendent Cory Wilson wants a smaller bond. “There’s a lot of work,” Wilson said."
    assert introduce_speakers(already, text) == already
    assert introduce_speakers("“We found him,” Police said.", "Fort Worth Police said they found him.") == "“We found him,” Police said."
    assert introduce_speakers("Cory Wilson said the bond matters.", text) == "Cory Wilson said the bond matters."


def test_render_175_rules():
    """Nov 23, render 175: three drafts, three hand fixes.
    CBS Texas's "Cowboys, Salvation Army to illuminate AT&T Stadium red" captioned only its dek about money raised: the two
    sentences announcing the lighting ceremony ran past the length limit and were dropped whole.
    FOX 4's blood-drive raffle repeated the 12:15 post on the same Cowboys and Carter BloodCare blood drive.
    Variety's "Avengers: Doomsday Won't Screen for BAFTA, Golden Globes ..." took the national slot with a cosplayer photo."""
    from ftworthtv.filters import awards_trade, same_event
    from ftworthtv.images.providers import PhotoCandidate, not_a_photo
    from ftworthtv.writer import _sentences, trim_trailing_phrase
    summary = ("Since joining forces, the Cowboys and The Salvation Army have helped raise more than $3.4 billion through their "
               "partnership. November 23, 2026 / 5:16 PM CST / CBS Texas The Dallas Cowboys and The Salvation Army will mark a major "
               "milestone in their 30-year partnership with a first-of-its-kind lighting ceremony at AT&T Stadium on Monday, kicking "
               "off Thanksgiving week and celebrating the annual Red Kettle Campaign. Four generations of the Gene and Jerry Jones "
               "family will gather to illuminate AT&T Stadium's exterior in red, recognizing three decades of working together and "
               "the organizations' shared commitment to helping individuals and families in need. Since joining forces, the Cowboys "
               "and The Salvation Army have helped raise more than $3.4 billion through their partnership.")
    out = _sentences(summary)
    assert out[0] == ("The Dallas Cowboys and The Salvation Army will mark a major milestone in their 30-year partnership with a "
                      "first-of-its-kind lighting ceremony at AT&T Stadium on Monday.")
    assert out[1] == "Four generations of the Gene and Jerry Jones family will gather to illuminate AT&T Stadium's exterior in red."
    long_said = ("Fort Worth police officers said Monday, citing a long report from the department's homicide unit and two witnesses "
                 "at the scene, that the man had been shot after an argument outside the convenience store on East Berry Street.")
    assert trim_trailing_phrase(long_said, 120) == ""                    # never cut a sentence down to "police said Monday."
    blood = ("Donors who participated in a blood drive at AT&T Stadium might win tickets. On Monday, November 23, the Dallas Cowboys "
             "teamed up with Carter BloodCare to host a blood drive at AT&T Stadium in Arlington.")
    assert same_event("Dallas Cowboys raffle off Thanksgiving game tickets for blood drive donors", blood,
                      "Dallas Cowboys partner with Carter BloodCare to host blood drive ahead of Thanksgiving")
    assert not same_event("Fort Worth forecast for Tuesday, November 24", "A cold Monday night gives way to a sunny Tuesday.",
                          "Fort Worth forecast for Monday, November 23")
    assert not same_event("Fort Worth police investigate shooting at East Berry gas station", "Fort Worth police said a man was shot.",
                          "Fort Worth police investigate shooting on East Lancaster Avenue")
    assert awards_trade("Marvel’s ‘Avengers: Doomsday’ Won’t Screen for BAFTA, Golden Globes and Other Early Awards Groups")
    assert not awards_trade("Oscars 2027: The full list of winners")
    assert not awards_trade("Golden Globes nominations: 'Wicked' leads the pack")
    cosplay = PhotoCandidate(id="c", url="https://upload.wikimedia.org/x.jpg", credit="Photo: Mickey83 via Wikimedia Commons (CC BY-SA 4.0)",
                             license="wikimedia-cc", provider="wikimedia",
                             source_url="https://commons.wikimedia.org/wiki/File:Cosplayer_di_Scarlet_(Marvel_Cinematic_Universe)_a_Levante_For_2024,_Bari.jpg",
                             title="Cosplayer di Scarlet (Marvel Cinematic Universe) a Levante For 2024, Bari")
    assert not_a_photo(cosplay)


def test_render_176_rules():
    """Nov 23, render 176: KVUE's "Mexico demands SpaceX clean up suspected rocket debris washing ashore near Texas" drew a
    SpaceX hangar at Kennedy Space Center, Florida, and was filed as breaking news for "explosion" in its lead."""
    from ftworthtv.filters import infer_category
    from ftworthtv.images.subject import happened
    from ftworthtv.models import Story
    title = "Mexico demands SpaceX clean up suspected rocket debris washing ashore near Texas"
    lead = ("Suspected debris from a SpaceX rocket explosion has washed up in Mexico, prompting cleanup efforts and new questions "
            "about environmental risks near Texas.")
    assert happened(title)
    def mk(t, summary, scope):
        return Story(id="x", source="KVUE Austin", source_kind="rss", title=t, summary=summary, url="https://e.com", extra={"scope": scope})
    assert infer_category(mk(title, lead, "texas")) != "breaking"
    assert infer_category(mk("Explosion rocks chemical plant near Houston", "Crews responded to the explosion.", "texas")) == "breaking"
    assert infer_category(mk("Crews respond to east Fort Worth business", "An explosion shook the building.", "local")) == "breaking"


def test_render_177_rules(settings, now):
    """Nov 23, render 177: FOX 4's "Police, SWAT units responding after 1 shot by barricaded suspect in Arlington home" waited
    behind the day's crime cap forty minutes after it broke: a police scene still under way is breaking news."""
    from ftworthtv.filters import active_scene, filter_stories
    from ftworthtv.models import Story
    from ftworthtv.state import State
    assert active_scene("Police, SWAT units responding after 1 shot by barricaded suspect in Arlington home")
    assert not active_scene("SWAT standoff ends with suspect in custody in east Fort Worth")
    assert not active_scene("Man shot outside Fort Worth convenience store")
    s = Story(id="swat", source="FOX 4 Dallas-Fort Worth", source_kind="rss",
              title="Police, SWAT units responding after 1 shot by barricaded suspect in Arlington home",
              summary="Arlington police and SWAT units are responding to a home where a barricaded suspect shot one person.",
              url="https://www.fox4news.com/news/arlington-swat", published=now)
    kept, dropped = filter_stories([s], settings, State(settings.state_path), now)
    assert kept and kept[0].category == "breaking" and kept[0].is_urgent
