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
