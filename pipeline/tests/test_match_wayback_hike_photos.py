"""Tests for match_wayback_hike_photos.py - joining the recovered NYNJTC
photographs to the hikes they belong to (#1450).

No network: this stage is pure arithmetic over two caches.

The load-bearing tests here are the REFUSALS, and that is the point of the
module. 403 photographs against 385 hikes is 155,155 candidate pairs, and
every filename in the corpus contains a word like "trail", "view" or
"mountain" that every hike also contains. A matcher that scored those would
pair everything with everything and report it as coverage - which is the
shape of the failure features/POI_PHOTOS.md already paid for once, when a
photograph of an Asiatic dayflower passed every automatic bar there was and
would have been shown as Gravel Springs Hut Shelter.
"""

import json

import pytest

import match_wayback_hike_photos as match


def _photo(subject, digest="d1", credit=None, width=250, height=188):
    return match.Photo(
        digest=digest,
        subject=subject,
        filename=f"{subject}.jpg",
        credit=credit,
        width=width,
        height=height,
        original_url=f"https://www.nynjtc.org/sites/default/files/u26/{subject}.jpg",
        timestamp="20240103091500",
    )


def _hike(name, park="", region="", description="", hike_id="1"):
    return match.Hike(hike_id=hike_id, name=name, park=park, region=region, description=description, lat=41.0, lon=-74.0)


# --- what makes a word distinctive ---------------------------------------------


@pytest.mark.parametrize("word", ["trail", "view", "mountain", "lake", "bridge", "loop", "falls", "the"])
def test_a_word_every_hike_shares_is_not_evidence(word):
    """These appear in most of the 403 filenames and most of the 385 hikes.
    Scoring them would make every pair look supported."""
    assert match.distinctive_terms(word) == set()


def test_the_words_that_separate_one_place_from_another_survive():
    terms = match.distinctive_terms("Beaver Lodge in swamp on Terrace Pond South Trail")
    assert "terrace" in terms
    assert "beaver" in terms
    assert "trail" not in terms
    assert "south" not in terms


def test_a_photo_whose_subject_is_all_generic_words_matches_nothing():
    """ "Boardwalk along Yellow and Blue Trails" is a real filename in this
    corpus and names no place. It must produce no pairing rather than a weak
    one, because a weak pairing is a row somebody has to read and reject."""
    assert match.score_pair(_photo("view from the trail"), _hike("Some Loop", description="a trail with a view")) is None


# --- the refusals --------------------------------------------------------------


def test_the_same_park_is_not_evidence_about_which_hike():
    """A park holds dozens of these hikes, so park agreement can corroborate a
    landmark and can never carry a pairing by itself. Refused rather than
    ranked low: a sheet full of "same park" rows buries the ones worth
    reading."""
    photo = _photo("Wawayanda boardwalk")
    hike = _hike("Some Other Loop", park="Wawayanda State Park", description="a walk in the woods")

    assert match.score_pair(photo, hike) is None


def test_a_landmark_in_the_description_does_carry_a_pairing():
    """The maintainer's first signal, and the strongest one available: both
    sides were written by the same people about the same ground."""
    photo = _photo("Beaver Lodge in swamp on Terrace Pond South Trail")
    hike = _hike("A Loop", park="Wawayanda State Park", description="follows the Terrace Pond South Trail north")

    pairing = match.score_pair(photo, hike)

    assert pairing is not None
    assert "terrace" in pairing.on_description


def test_a_landmark_in_the_hikes_own_name_scores_higher_than_one_in_its_prose():
    """A title is chosen to identify the walk, so sharing it is the least
    ambiguous evidence this matcher can see."""
    photo = _photo("Terrace Pond in winter")
    by_name = match.score_pair(photo, _hike("Terrace Pond North Loop", description="a walk"))
    by_prose = match.score_pair(photo, _hike("Some Loop", description="passes Terrace Pond"))

    assert by_name.score > by_prose.score


def test_two_adjacent_distinctive_words_beat_the_same_two_scattered():
    """ "Terrace Pond" as a phrase is a place's name. The same two words in
    different sentences is a coincidence, and the gap between those is most of
    what separates a good pairing from a plausible one."""
    photo = _photo("Terrace Pond outlet")
    together = match.score_pair(photo, _hike("A Loop", description="reaches Terrace Pond and turns"))
    apart = match.score_pair(photo, _hike("A Loop", description="the terrace steps, then a pond"))

    assert together.score > apart.score
    assert together.phrases


# --- ranking, and keeping the alternatives -------------------------------------


def test_every_photo_keeps_its_runners_up():
    """A photograph whose top two candidates are a point apart is exactly
    where the automatic answer is least trustworthy, so the sheet has to show
    a person what it nearly chose."""
    photos = [_photo("Terrace Pond South Trail")]
    hikes = [
        _hike("Terrace Pond North Loop", hike_id="1"),
        _hike("Terrace Pond South Loop", hike_id="2"),
        _hike("Bearfort Ridge Loop", hike_id="3", description="climbs to Terrace Pond"),
    ]

    ranked = match.best_pairings(photos, hikes)

    assert len(ranked["d1"]) >= 2
    assert ranked["d1"][0].score >= ranked["d1"][1].score


def test_a_photo_matching_nothing_is_recorded_as_matching_nothing():
    ranked = match.best_pairings([_photo("view from the trail")], [_hike("Bearfort Ridge Loop")])

    assert ranked["d1"] == []


# --- the frame the card would give it ------------------------------------------


@pytest.mark.parametrize(
    ("width", "expected"),
    [(4000, "hero"), (640, "hero"), (639, "inset"), (250, "inset"), (None, "unknown")],
)
def test_the_frame_follows_the_images_natural_width(width, expected):
    """The maintainer's decision: a hero box for a real photograph, a crisp
    inset at native aspect below it, rather than upscaling a 250px rendition
    2.1x and cropping it to 16:10."""
    assert _photo("x", width=width).frame == expected


# --- the sheet and what it refuses to do ---------------------------------------


def test_the_sheet_shows_every_photo_including_the_weak_ones(tmp_path):
    """A low score on a correct pairing is a fact about this matcher, not
    about the photograph, so the sheet shows it shaded rather than hiding
    it."""
    photos = [_photo("Terrace Pond South Trail", digest="d1"), _photo("Bearfort Ridge cliffs", digest="d2")]
    hikes = [_hike("Terrace Pond North Loop", hike_id="1")]
    ranked = match.best_pairings(photos, hikes)
    sheet = tmp_path / "sheet.html"

    match.write_sheet(ranked, photos, 0.5, sheet)

    written = sheet.read_text(encoding="utf-8")
    assert "Terrace Pond North Loop" in written
    assert "d1.jpg" in written  # the photograph is rendered, not just named


def test_the_sheet_says_the_score_is_not_a_probability(tmp_path):
    """#1450's standard is what a person confirms. A sheet that presented an
    uncalibrated rank as a likelihood would invite exactly the automatic
    confidence this whole exercise exists to refuse."""
    sheet = tmp_path / "sheet.html"

    match.write_sheet({}, [], 0.5, sheet)

    written = sheet.read_text(encoding="utf-8")
    assert "not a probability" in written
    assert "dayflower" in written


def test_a_photo_subject_is_escaped_into_the_sheet(tmp_path):
    """These filenames come off a public archive and land in a local HTML
    file somebody opens."""
    photos = [_photo('Nasty <script>alert("x")</script> Pond', digest="d1")]
    hikes = [_hike("Nasty Pond Loop", hike_id="1")]
    sheet = tmp_path / "sheet.html"

    match.write_sheet(match.best_pairings(photos, hikes), photos, 0.5, sheet)

    assert "<script>alert" not in sheet.read_text(encoding="utf-8")


# --- loading -------------------------------------------------------------------


def test_a_description_stored_as_paragraphs_is_joined(tmp_path):
    """The export stores the write-up as a list, and a landmark can be in any
    paragraph - so reading only the first would lose most of the signal."""
    path = tmp_path / "hikefinder.json"
    path.write_text(
        json.dumps({"hikes": {"7": {"name": "A Loop", "description": ["first para", "reaches Terrace Pond"]}}}),
        encoding="utf-8",
    )

    hikes = match.load_hikes(path)

    assert "terrace" in hikes[0].description_terms


def test_a_missing_export_says_where_the_secret_lives(capsys, monkeypatch, tmp_path):
    """The blocker a sandbox actually hits: HIKEFINDER_PASSWORD is a GitHub
    Actions secret, so this match runs in CI and not on a laptop. Saying only
    "missing" would send the next reader hunting for a file."""
    monkeypatch.setattr(match, "PHOTOS_PATH", tmp_path / "photos.json")
    (tmp_path / "photos.json").write_text(json.dumps({"photos": [{"digest": "d", "subject": "Terrace Pond"}]}), encoding="utf-8")
    monkeypatch.setattr(match, "HIKES_PATH", tmp_path / "nope.json")

    assert match.main(0.5) == 1
    assert "HIKEFINDER_PASSWORD" in capsys.readouterr().out


def test_an_unknown_flag_is_rejected_rather_than_silently_ignored():
    with pytest.raises(SystemExit) as excinfo:
        match.run(["--minimum", "0.5"])

    assert excinfo.value.code == 2


# --- the two failures the 2026-09-15 trial actually produced -------------------


def test_one_shared_word_lands_below_the_default_floor():
    """ "Black Rock from Mt. Misery" matched "Black Creek Preserve Loop" on the
    single word "black" and scored 1.80. It is the wrong hike. The matcher is
    not asked to refuse it - one word IS weak evidence rather than none - but
    it must not reach the floor the sheet puts above the fold."""
    pairing = match.score_pair(_photo("Black Rock from Mt. Misery"), _hike("Black Creek Preserve Loop", description="a walk"))

    assert pairing is not None
    assert pairing.score < match.DEFAULT_MIN_SCORE


def test_a_phrase_naming_a_feature_rather_than_a_place_lands_below_it_too():
    """ "Beaver lodge" is a real shared phrase and several of these hikes pass
    one, so it scored 2.10 onto a hike it does not belong to. Same verdict: a
    single weak signal stays below the fold."""
    pairing = match.score_pair(_photo("Beaver lodge"), _hike("Terrace Pond North Loop", description="past a beaver lodge"))

    assert pairing is not None
    assert pairing.score < match.DEFAULT_MIN_SCORE


def test_the_trials_correct_pairings_clear_the_floor():
    """The other half of the same evidence: the pairings a person confirmed
    all sit above it, so the floor separates the bands rather than just being
    high."""
    good = [
        (
            _photo("Anthony's Nose from the Major Welch Trail along Hessian Lake"),
            _hike("Major Welch Trail to Bear Mountain", description="the Major Welch Trail climbs above Hessian Lake"),
        ),
        (
            _photo("Balsam Lake Mountain fire tower 2"),
            _hike("Balsam Lake Mountain Loop", description="climbs to the Balsam Lake Mountain fire tower"),
        ),
        (
            _photo("Beaver Lodge in swamp on Terrace Pond South Trail"),
            _hike("Terrace Pond North Loop", description="climbs the Terrace Pond South Trail past a beaver lodge"),
        ),
    ]
    for photo, hike in good:
        assert match.score_pair(photo, hike).score >= match.DEFAULT_MIN_SCORE


# --- the page join: a fact, not a score ----------------------------------------
#
# These are the tests for the reorder of 2026-09-15. The maintainer asked
# whether this was matching on name and said to try location and distance
# first; it was, and the answer turned out to be that the strongest signal is
# not a signal - NYNJTC published which photograph belonged to which hike, and
# the archive kept it. What follows pins that the join is READ, that distance
# only ever narrows, and that the one row which can never ship is ranked last.


def _page(name, photos, lat=41.0, lon=-74.0, park="", region="", description="", url=None, credit="Daniel Chazin"):
    """A write-up whose photographs are CREDITED unless a test says otherwise.

    Credited by default so the tests below stay about the join and the
    ranking, which is what they were written for. The licence gate that
    `credit=None` exercises has its own tests at the end of this file, where a
    reader looking for it will find it named rather than inferred from a
    fixture's default (#1504).
    """
    photos = [
        photo if isinstance(photo, match.PagePhoto) else match.PagePhoto(filename=photo, credit=credit, credit_basis="img")
        for photo in photos
    ]
    return match.Page(
        url=url or f"https://www.nynjtc.org/hike/{name.lower().replace(' ', '-')}",
        timestamp="20240103091500",
        name=name,
        park=park,
        region=region,
        lat=lat,
        lon=lon,
        description=description,
        photos=photos,
    )


def test_a_photograph_on_a_write_up_is_joined_rather_than_scored():
    """THE test for the reorder. The photograph's subject shares not one word
    with the hike, so every text route scores it zero - and it is still
    matched, because NYNJTC printed it on that hike's page."""
    photo = _photo("DSC00417", digest="d1")
    hike = _hike("Terrace Pond South Loop", description="A quiet loop.")
    page = _page("Terrace Pond South Loop", ["DSC00417.jpg"])

    ranked = match.best_pairings([photo], [hike], [page])
    top = ranked["d1"][0]

    assert top.basis == match.BASIS_PAGE_NAME
    assert top.hike.hike_id == "1"
    assert top.score == 0.0  # the words really do say nothing
    assert top.placed_by_page


def test_the_page_join_survives_a_drupal_derivative_token():
    """The same file is cited as `name.jpg` on one capture and
    `name.jpg?itok=...` on another. Two spellings failing to join would look
    exactly like a photograph NYNJTC never published."""
    photo = _photo("Beaver Lodge", digest="d1")
    photo = match.Photo(**{**photo.__dict__, "filename": "Beaver Lodge.jpg?itok=9Kd2"})
    page = _page("Terrace Pond South Loop", ["Beaver Lodge.jpg"])

    ranked = match.best_pairings([photo], [_hike("Terrace Pond South Loop")], [page])

    assert ranked["d1"][0].basis == match.BASIS_PAGE_NAME


def test_the_page_join_ignores_the_filenames_case():
    photo = _photo("x", digest="d1")
    photo = match.Photo(**{**photo.__dict__, "filename": "Sunfish_Pond.JPG"})
    page = _page("Sunfish Pond Loop", ["sunfish_pond.jpg"])

    ranked = match.best_pairings([photo], [_hike("Sunfish Pond Loop")], [page])

    assert ranked["d1"][0].basis == match.BASIS_PAGE_NAME


@pytest.mark.parametrize(
    ("archived", "exported"),
    [
        ("Mt. Minsi Loop", "Mount Minsi Loop"),
        ("Bear Mountain  Loop", "Bear Mountain Loop"),
        ("Anthony's Nose", "Anthonys Nose"),
        ("HARRIMAN: Pine Meadow", "Harriman - Pine Meadow"),
    ],
)
def test_two_spellings_of_one_title_are_the_same_walk(archived, exported):
    assert match.normalise_title(archived) == match.normalise_title(exported)


@pytest.mark.parametrize(
    ("one", "other"),
    [
        ("Terrace Pond North Loop", "Terrace Pond North Trail"),
        ("Terrace Pond North Loop", "Terrace Pond South Loop"),
        ("Mount Minsi Loop", "Mount Tammany Loop"),
    ],
)
def test_titles_that_name_different_walks_are_kept_apart(one, other):
    """`normalise_title` forgives punctuation and a handful of abbreviations
    and NOTHING ELSE. Dropping "loop" and "trail" as noise would collapse two
    real, different walks into one confident wrong join."""
    assert match.normalise_title(one) != match.normalise_title(other)


def test_a_title_that_does_not_match_falls_to_the_nearby_route():
    """The archive's title and the export's are not always the same string.
    A shared distinctive word plus proximity is the weaker second route."""
    hike = _hike("Mount Minsi Loop")  # at 41.0, -74.0
    page = _page("Mt. Minsi via the Appalachian Trail", ["v.jpg"], lat=41.001, lon=-74.001)

    resolved = match.resolve_page(page, [hike])

    assert resolved is not None
    chosen, basis, metres = resolved
    assert chosen.hike_id == "1"
    assert basis == match.BASIS_PAGE_NEAR
    assert metres < 200


def test_distance_alone_never_places_a_write_up():
    """THE refusal this route needs, and the same shape as the park-alone
    refusal above. Two unrelated walks routinely start from one car park, so
    "nearest" is not an answer to "which"."""
    hike = _hike("Sterling Ridge Trail")
    page = _page("Wawayanda Swamp Walk", ["v.jpg"], lat=41.0, lon=-74.0)  # 0 m apart

    assert match.resolve_page(page, [hike]) is None


def test_a_write_up_beyond_the_bound_is_not_a_candidate():
    hike = _hike("Minsi Loop")  # 41.0, -74.0
    far = _page("Minsi Walk", ["v.jpg"], lat=42.0, lon=-74.0)  # ~111 km

    assert match.resolve_page(far, [hike]) is None


def test_the_join_bound_is_generous_because_a_tight_one_loses_rows():
    """Pinned as the argument rather than as a number. Nobody has yet seen
    whether these coordinates point at a trailhead or at a park, and the
    expensive failure is dropping a correct row - which looks identical to a
    photograph nobody could place. It is affordable only because
    `resolve_page` also requires title agreement."""
    assert match.MAX_JOIN_METRES >= 2_000.0


def test_a_write_up_the_export_does_not_have_is_shown_but_cannot_ship():
    photo = _photo("DSC00417", digest="d1")
    page = _page("Some Walk NYNJTC Dropped", ["DSC00417.jpg"])

    ranked = match.best_pairings([photo], [_hike("Something Else Entirely")], [page])
    top = ranked["d1"][0]

    assert top.basis == match.BASIS_PAGE_ONLY
    assert top.hike.hike_id == ""  # nothing to attach a photograph to
    assert not top.placed_by_page
    assert "place it by hand" in match._reasons(top)


def test_a_page_only_row_never_leads_the_sheet():
    """Ranked LAST, under even the weakest text match. The first draft had it
    third, above every text row, on the reasoning that it was the more certain
    answer - which it is, and it is certain about a write-up rather than about
    a photograph anyone can ship. Ranking certainty above usefulness buries
    every correct text match under work that cannot end in a photograph."""
    # CREDITED, so this pins the page-only rule rather than the licence gate.
    # Without it `publishable` is False and the assertion below holds whatever
    # `above_the_fold` does with `placed_by_page` - which review caught.
    credited = match.PagePhoto("x.jpg", "Daniel Chazin", "img")
    unplaceable = match.Pairing(
        _photo("x"), _hike("Gone"), 0.0, basis=match.BASIS_PAGE_ONLY, page=_page("Gone", []), shown_as=credited
    )
    weak_text = match.Pairing(_photo("y"), _hike("Real"), 0.01, basis=match.BASIS_SUBJECT)

    assert unplaceable.publishable, "or this proves the credit gate, not the page-only rule"
    assert weak_text.rank < unplaceable.rank
    assert not match.above_the_fold(unplaceable, minimum=2.5)


def test_a_placed_page_row_leads_even_when_the_words_share_nothing():
    placed = match.Pairing(
        _photo("DSC00417"),
        _hike("Real"),
        0.0,
        basis=match.BASIS_PAGE_NAME,
        shown_as=match.PagePhoto("DSC00417.jpg", "Daniel Chazin", "img"),
    )

    assert match.above_the_fold(placed, minimum=2.5)


def test_the_page_and_the_words_disagreeing_is_surfaced_not_resolved():
    """Either the text matcher is wrong in a way worth seeing, or a write-up
    reused a photograph from another walk. Both are a person's call."""
    photo = _photo("Terrace Pond ice at Wawayanda", digest="d1")
    published_on = _hike("Bearfort Ridge Walk", hike_id="1")
    the_words_prefer = _hike("Terrace Pond North Loop", hike_id="2", description="Ice on Terrace Pond in Wawayanda.")
    page = _page("Bearfort Ridge Walk", ["Terrace Pond ice at Wawayanda.jpg"])

    ranked = match.best_pairings([photo], [published_on, the_words_prefer], [page])

    assert ranked["d1"][0].hike.hike_id == "1"
    assert match.disagrees(ranked["d1"], minimum=2.5)


def test_the_rows_where_they_disagree_come_first(tmp_path):
    photo = _photo("Terrace Pond ice at Wawayanda", digest="d1")
    quiet = _photo("DSC00417", digest="d2")
    published_on = _hike("Bearfort Ridge Walk", hike_id="1")
    elsewhere = _hike("Terrace Pond North Loop", hike_id="2", description="Ice on Terrace Pond in Wawayanda.")
    pages = [
        _page("Bearfort Ridge Walk", ["Terrace Pond ice at Wawayanda.jpg"]),
        _page("Terrace Pond North Loop", ["DSC00417.jpg"], url="https://www.nynjtc.org/hike/tp"),
    ]

    ranked = match.best_pairings([photo, quiet], [published_on, elsewhere], pages)
    sheet = tmp_path / "sheet.html"
    match.write_sheet(ranked, [photo, quiet], 2.5, sheet)
    document = sheet.read_text(encoding="utf-8")

    assert document.index("Terrace Pond ice at Wawayanda") < document.index("DSC00417")
    assert "the page and the words point at different hikes" in document


def test_a_photograph_cited_by_two_write_ups_keeps_the_first():
    """Not silent, and not settled by a sort order: `main()` counts these, and
    a reviewer decides which walk a reused photograph belongs to."""
    shared = ["same.jpg"]
    first = _page("First Walk", shared, url="https://www.nynjtc.org/hike/a")
    second = _page("Second Walk", shared, url="https://www.nynjtc.org/hike/b")

    page, shown_as = match.pages_by_photo([first, second])["same.jpg"]

    assert page.name == "First Walk"
    assert shown_as.filename == "same.jpg"


def test_the_matcher_still_means_what_it_meant_with_no_write_ups():
    """The write-up recovery is a separate, slow leg. A photographs-only run
    must still produce the old sheet rather than an empty one."""
    photo = _photo("Terrace Pond in winter", digest="d1")
    hike = _hike("Terrace Pond North Loop", description="Ice on Terrace Pond.")

    ranked = match.best_pairings([photo], [hike])

    assert ranked["d1"][0].basis == match.BASIS_SUBJECT
    assert ranked["d1"][0].score > 0


@pytest.mark.parametrize("content", ["", "{", '{"pages": "not a list"}', '{"no": "pages"}'])
def test_a_broken_page_cache_is_empty_rather_than_an_exception(tmp_path, content):
    """An unreadable cache must degrade to the text route, not stop the run."""
    broken = tmp_path / "wayback_hike_pages.json"
    broken.write_text(content, encoding="utf-8")

    assert match.load_pages(broken) == []


def test_load_pages_reads_exactly_what_the_fetcher_writes(tmp_path):
    """THE CONTRACT TEST between the two modules. The fetcher's record shape
    and the matcher's reader are written in different files and nothing but
    this makes them agree - a renamed field would otherwise show up as a join
    that quietly found nothing, which is indistinguishable in a count from a
    site that never published the pairing."""
    import fetch_wayback_hike_pages as fetcher

    written = fetcher.HikePage(
        url="https://www.nynjtc.org/hike/terrace-pond-south",
        timestamp="20240103091500",
        name="Terrace Pond South Loop",
        park="Wawayanda State Park",
        region="NJ Highlands",
        lat=41.15,
        lon=-74.37,
        description="A loop past a beaver lodge.",
        photos=[fetcher.PagePhoto(filename="Beaver_Lodge.jpg", credit="Daniel Chazin", credit_basis="img")],
    )
    cache = tmp_path / "wayback_hike_pages.json"
    fetcher.write_cache([written], ["https://www.nynjtc.org/hike/terrace-pond-south"], cache)

    read = match.load_pages(cache)

    assert len(read) == 1
    assert read[0].name == written.name
    # Field for field, ACROSS THE JSON: the credit is the licence's condition,
    # so a round trip that lost it would refuse photographs NYNJTC does
    # credit (#1504).
    assert read[0].photos == [match.PagePhoto("Beaver_Lodge.jpg", "Daniel Chazin", "img")]
    assert read[0].where == (written.lat, written.lon)


def test_metres_apart_is_none_when_either_side_has_no_coordinate():
    """Reported as unknown, never as zero. A missing coordinate that read as
    "0 m away" would make the nearby route confidently wrong."""
    nowhere = _page("A Walk", ["v.jpg"], lat=None, lon=None)
    somewhere = _page("A Walk", ["v.jpg"])
    placed = _hike("A Walk")
    unplaced = match.Hike("2", "A Walk", "", "", "", None, None)

    assert match.metres_apart(nowhere, placed) is None
    assert match.metres_apart(somewhere, unplaced) is None


def test_a_page_with_no_coordinate_still_joins_on_its_title():
    """Route 2 does not need route 3. Plenty of these captures carry no
    coordinate at all, and a title both sides agree on is enough."""
    page = _page("Sunfish Pond Loop", ["v.jpg"], lat=None, lon=None)

    resolved = match.resolve_page(page, [_hike("Sunfish Pond Loop")])

    assert resolved is not None
    assert resolved[1] == match.BASIS_PAGE_NAME
    assert resolved[2] is None


def test_the_proposed_json_records_which_route_reached_each_row(tmp_path, monkeypatch):
    """A row read out of this file must not be able to lose the difference
    between a page join and a string comparison."""
    monkeypatch.setattr(match, "PROCESSED_DIR", tmp_path)
    monkeypatch.setattr(match, "PROPOSED_PATH", tmp_path / "matches.json")
    monkeypatch.setattr(match, "SHEET_PATH", tmp_path / "sheet.html")
    monkeypatch.setattr(match, "load_photos", lambda: [_photo("DSC00417", digest="d1")])
    monkeypatch.setattr(match, "load_hikes", lambda: [_hike("Terrace Pond South Loop")])
    monkeypatch.setattr(match, "load_pages", lambda: [_page("Terrace Pond South Loop", ["DSC00417.jpg"])])

    assert match.main(2.5) == 0

    proposed = json.loads((tmp_path / "matches.json").read_text(encoding="utf-8"))
    row = proposed["matches"][0]
    assert row["basis"] == match.BASIS_PAGE_NAME
    assert row["page_title"] == "Terrace Pond South Loop"
    assert row["page_url"].endswith("/terrace-pond-south-loop")
    assert proposed["write_ups"] == 1


# --- the licence gate (#1504) --------------------------------------------------
#
# `sources.json`'s `nynjtc_hikes_licence` conditions the whole permission on the
# credit: "the attribution is a condition rather than a courtesy ... a photograph
# the page does not credit is not fetched at all". The recovery this matcher reads
# selected photographs by DIRECTORY PREFIX - `u26` is a site-wide upload folder,
# wider than the Favorite Hikes the permission covers - so the credit is the only
# thing separating a photograph this project may publish from one it may not.
#
# What follows pins the gate in both directions: nothing uncredited can ship, and
# nothing credited is lost to it.


def _run_main(tmp_path, monkeypatch, photos, hikes, pages):
    monkeypatch.setattr(match, "PROCESSED_DIR", tmp_path)
    monkeypatch.setattr(match, "PROPOSED_PATH", tmp_path / "matches.json")
    monkeypatch.setattr(match, "SHEET_PATH", tmp_path / "sheet.html")
    monkeypatch.setattr(match, "load_photos", lambda: photos)
    monkeypatch.setattr(match, "load_hikes", lambda: hikes)
    monkeypatch.setattr(match, "load_pages", lambda: pages)
    assert match.main(2.5) == 0
    return (
        json.loads((tmp_path / "matches.json").read_text(encoding="utf-8")),
        (tmp_path / "sheet.html").read_text(encoding="utf-8"),
    )


def test_an_uncredited_photograph_never_reaches_the_proposed_file(tmp_path, monkeypatch):
    """THE GATE. This row is as strong as this matcher gets - NYNJTC printed the
    photograph on that hike's own page and both call the walk the same thing -
    and it still cannot ship, because nothing names the photographer. The
    pairing being right is not the question the licence asks."""
    proposed, _ = _run_main(
        tmp_path,
        monkeypatch,
        photos=[_photo("DSC00417", digest="d1")],
        hikes=[_hike("Terrace Pond South Loop")],
        pages=[_page("Terrace Pond South Loop", ["DSC00417.jpg"], credit=None)],
    )

    assert proposed["matches"] == []
    assert proposed["withheld_uncredited"] == 1


def test_a_credited_photograph_still_reaches_it_and_says_where_the_name_came_from(tmp_path, monkeypatch):
    """The other direction, because a gate that refuses everything is not a
    gate. The credit travels into the file beside the pairing, so a row copied
    out of it cannot lose the attribution the licence requires."""
    proposed, _ = _run_main(
        tmp_path,
        monkeypatch,
        photos=[_photo("DSC00417", digest="d1")],
        hikes=[_hike("Terrace Pond South Loop")],
        pages=[_page("Terrace Pond South Loop", ["DSC00417.jpg"], credit="Daniel Chazin")],
    )

    assert proposed["withheld_uncredited"] == 0
    assert proposed["matches"][0]["credit"] == "Daniel Chazin"
    assert proposed["matches"][0]["credit_basis"] == "page, img"


def test_the_uncredited_row_is_still_shown_so_the_gap_has_a_size(tmp_path, monkeypatch):
    """Refused, not subtracted. How many photographs the permission does not
    cover is a fact about this corpus worth seeing - and a reviewer who finds
    the credit somewhere this parser did not look needs the row in front of
    them to say so."""
    _, sheet = _run_main(
        tmp_path,
        monkeypatch,
        photos=[_photo("DSC00417", digest="d1")],
        hikes=[_hike("Terrace Pond South Loop")],
        pages=[_page("Terrace Pond South Loop", ["DSC00417.jpg"], credit=None)],
    )

    assert "DSC00417" in sheet
    assert "uncredited" in sheet
    assert "cannot ship" in sheet


def test_an_uncredited_row_cannot_lead_the_sheet_by_any_route(tmp_path, monkeypatch):
    """Not the page join, and not a high text score either. Both routes answer
    "which hike"; neither answers "may we publish it"."""
    photo = _photo("Beaver Lodge in swamp on Terrace Pond South Trail", digest="d1")
    hike = _hike("Terrace Pond South Loop", description="follows the Terrace Pond South Trail past a beaver lodge")

    by_text = match.score_pair(photo, hike)
    assert by_text.score >= 2.5, "fixture must score above the line, or this proves nothing"
    assert not match.above_the_fold(by_text, minimum=2.5)

    by_page = match.Pairing(photo, hike, 0.0, basis=match.BASIS_PAGE_NAME)
    assert not match.above_the_fold(by_page, minimum=2.5)


def test_the_page_credit_beats_the_one_in_the_filename():
    """ "The credit line the page carries" is the licence's own wording, so a
    name NYNJTC wrote in their prose outranks one this build read out of a file
    name - and the basis says which, because they are not equally strong."""
    pairing = match.Pairing(
        _photo("DSC00417", credit="From The Filename"),
        _hike("Real"),
        0.0,
        basis=match.BASIS_PAGE_NAME,
        shown_as=match.PagePhoto("DSC00417.jpg", "Daniel Chazin", "caption"),
    )

    assert pairing.credit == "Daniel Chazin"
    assert pairing.credit_basis == "page, caption"


def test_a_credit_in_the_filename_alone_is_accepted_and_labelled_as_such():
    """A judgement this build is making, not the licence's own words: NYNJTC
    wrote the photographer into the file name and a write-up published that
    name in its `src`. Labelled `filename` so a reviewer reading the condition
    more strictly can find those rows and refuse them."""
    pairing = match.Pairing(
        _photo("DSC00417", credit="Daniel Chazin"),
        _hike("Real"),
        0.0,
        basis=match.BASIS_PAGE_NAME,
        page=_page("Real", ["DSC00417.jpg"], credit=None),
        shown_as=match.PagePhoto("DSC00417.jpg", None, None),
    )

    assert pairing.publishable
    assert pairing.credit_basis == "filename"


def test_a_filename_credit_with_no_write_up_behind_it_is_not_a_credit():
    """The filename route's whole justification is that a write-up published
    that name in its `src`. With no recovered write-up there is no page
    carrying anything, so the justification is an empty sentence - and the
    licence's words are "the credit line the PAGE carries". The first version
    accepted it anyway, which review caught."""
    pairing = match.Pairing(_photo("DSC00417", credit="Daniel Chazin"), _hike("Real"), 4.0)

    assert pairing.page is None
    assert not pairing.publishable
    assert pairing.credit_basis is None
    assert not match.above_the_fold(pairing, minimum=2.5)


def test_the_credit_basis_names_the_route_once():
    """It is printed in the sheet and written into the proposed file, so it is
    the provenance string a reviewer is told to read. An earlier version
    prefixed "page, " onto a basis that already began "page,"."""
    pairing = match.Pairing(
        _photo("DSC00417"),
        _hike("Real"),
        0.0,
        basis=match.BASIS_PAGE_NAME,
        shown_as=match.PagePhoto("DSC00417.jpg", "Jane Daniels", "caption"),
    )

    assert pairing.credit_basis == "page, caption"


def test_a_cache_written_before_the_gate_existed_is_refused_rather_than_trusted():
    """An old cache holds bare filenames, which means "nobody looked for a
    credit" and not "there is none" - and this module cannot tell those apart.
    Under a licence conditioned on the credit, the unreadable case resolves to
    refused: re-run the write-up recovery rather than publish on a guess."""
    old_shape = {"url": "u", "photos": ["Beaver_Lodge.jpg"]}

    assert match.page_photos_of(old_shape) == [match.PagePhoto("Beaver_Lodge.jpg", None, None)]
    assert not match.Pairing(
        _photo("Beaver_Lodge", digest="d1"),
        _hike("Real"),
        0.0,
        basis=match.BASIS_PAGE_NAME,
        shown_as=match.page_photos_of(old_shape)[0],
    ).publishable


def test_the_sheet_says_the_refusal_is_the_licence_and_not_the_matcher(tmp_path, monkeypatch):
    """A reviewer who reads "no credit" as a scoring failure will try to fix it
    by improving the match, which cannot work. The sheet names the licence, the
    directory-prefix selection that caused it, and the issue."""
    _, sheet = _run_main(
        tmp_path,
        monkeypatch,
        photos=[_photo("DSC00417", digest="d1")],
        hikes=[_hike("Terrace Pond South Loop")],
        pages=[_page("Terrace Pond South Loop", ["DSC00417.jpg"], credit=None)],
    )

    assert "nynjtc_hikes_licence" in sheet
    assert "condition rather than a courtesy" in sheet
    assert "1504" in sheet


def test_the_sheet_renders_from_the_store_the_fetcher_actually_writes_to():
    """Two modules name that directory and they must not drift. If they do,
    the sheet is a page of broken image icons - and a review sheet nobody can
    see the pictures in cannot settle the one question (#1450) that only a
    person looking at the photograph can settle."""
    import fetch_wayback_hike_photos as fetcher

    assert match.ARCHIVE_STORE_DIRNAME == fetcher.ARCHIVE_STORE_DIRNAME
    assert match.ARCHIVE_STORE_DIRNAME != "poi_photos", "the published store is the one place these must never be"
