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
