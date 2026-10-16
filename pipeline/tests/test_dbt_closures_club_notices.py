"""int_closures__club_notices reads every notice by its own words against one vocabulary.

The maintainer, poll of 2026-10-14: "Do by their own words. But make this logic that applies everywhere. we need to
stop doing org by org customization." seeds/notice_words.csv is that vocabulary, and seeds/notice_word_overrides.csv
the one value no shared word can read. The model's unit tests mock both; this holds each mock to its file, so a test
cannot pass on a vocabulary the build does not use, and holds that no rule of the model names a source.

It also holds the maintainer's answers of 2026-10-11 on how club statuses read
to the shared words, where a later edit would otherwise move one without a word: Missouri's Archived alone is not
current (P1), Michigan's '-1' rows are nothing for a hiker by their own category, 'Motorized' (P4), a closed Florida
park closes its trails (P5) and is placed by its own boundary (seeds/notice_steward_areas.csv), the Great
Allegheny Passage's Hidden and Cleared are both not current (P6), and NETT's damaged bridges close by their own
words (P11). NGPC's sections read as their sources.json row settles: a Condition of 'Impassable' or 'Not
Passable' closes the trail however Road_Status reads. And the own cases, by IDPR's live rows of
2026-10-14: an order barring any use closes beside a note calling the trail non-motorized (2232), one barring the
trail on weekdays closes (3018), one possibly closed closes (2245), and the three barring motorized use alone are
nothing for a hiker. A category's 'closure' is the kind of notice, and closes only beside a title that names a
closure too: USFS's forest orders are typed 'Safety Closure' whatever they bar, 'Forest Wide - Alcohol' among them.
And the maintainer's three fixes (poll of 2026-10-15, "Add the 3 fixes"): a layer closes by its own name only where
that name says closures, a closed site is not a closed trail, and an area that names only roads closes no trail.

And the closures the review of 2026-10-15 found read as notices, each fixed as a reading for every source: a status no
word reads lets the title speak (S1-1), a flag's coded unknown leaves it a flag (S2-1), a title names each thing it
lists (S1-2), a start a title states with a day closes from that day (S1-4), a phrase naming both uses or everyone
bars every use (S2-2), a qualifying word inside a `not_a_qualifier` phrase qualifies nothing (S2-3), a closures
layer's detours and reopenings are not its closures (S2-4), a season a row states in words is read in the season
that has not ended (S1-3), and dates that contradict each other close no trail (S2-5). Its second pass found
facilities no site word named still crossed out (thread 4279221884): a dump station, a campground written 'CG', a
district office and ten more now read as sites, and the site words say they are a deny-list.

And the hazard areas (rule 6) are read by one standard for every hazard source: a category names its hazard
where its code, or its layer's label for the code, is a value seeds/notice_hazard_areas.csv lists, or holds one as
whole words beside no negating word. Until 2026-10-15 IATA's coded parcels and NY Parks' worded hunting areas were
held for want of an exact match.
"""

import csv
import re
from pathlib import Path

import yaml

from tests.notice_words import layer_closes, layer_name, readings, reads_as, seed, words_of

DBT = Path(__file__).resolve().parent.parent / "dbt"
CLOSURES = DBT / "models" / "intermediate" / "closures" / "_closures__intermediate.yml"
MODEL = DBT / "models" / "intermediate" / "closures" / "int_closures__club_notices.sql"
TEST = "int_closures__club_notices_keeps_an_ended_notice_without_closing_and_holds_back_what_its_status_says_is_not_current"
TEST_190 = "int_closures__club_notices_reads_a_notice_by_its_own_words_against_one_vocabulary_for_every_source"
TEST_REVIEW = "int_closures__club_notices_closes_by_a_status_no_word_reads_a_listed_trail_and_a_title_s_stated_start"
TEST_SEASON = (
    "int_closures__club_notices_reads_a_stated_season_in_the_season_that_has_not_ended_and_dates_that_contradict_as_"
    "closing_nothing"
)
TEST_FACILITIES = "int_closures__club_notices_reads_a_facility_its_title_names_as_a_site_and_a_trail_named_after_one_as_the_trail"
TEST_SHOWN = "int_closures__club_notices_shows_a_category_by_its_layers_own_label_and_names_a_bare_identifier_by_it"
TEST_HAZARD = (
    "int_closures__club_notices_reads_a_hazard_category_by_its_code_its_label_or_its_words_and_never_beside_a_negating_word"
)
#: The reading tests, which mock the whole vocabulary, and the tests that mock only the words they need.
WHOLE_VOCABULARY = (TEST, TEST_190, TEST_REVIEW)
SOME_WORDS = (
    "int_closures__club_notices_keeps_a_notice_for_a_days_margin_either_side_of_its_own_dates",
    "int_closures__club_notices_places_a_point_inside_exactly_one_of_its_stewards_own_areas_by_that_area",
    TEST_SEASON,
    TEST_FACILITIES,
    TEST_SHOWN,
    TEST_HAZARD,
    "int_closures__club_notices_reads_decision_213s_rules_for_every_source",
)


def _unit_tests() -> dict:
    return {test["name"]: test for test in yaml.safe_load(CLOSURES.read_text())["unit_tests"]}


def _given(test: dict, ref: str) -> list[dict]:
    (given,) = [g for g in test["given"] if g["input"] == f"ref('{ref}')"]
    return given["rows"]


def _expected(name: str) -> dict[str, dict]:
    return {row["notice_id"]: row for row in _unit_tests()[name]["expect"]["rows"]}


def test_every_reading_test_mocks_the_whole_vocabulary_as_the_seed_files_hold_it():
    tests = _unit_tests()
    for name in WHOLE_VOCABULARY:
        assert _given(tests[name], "notice_words") == seed("notice_words"), name
        assert _given(tests[name], "notice_word_overrides") == seed("notice_word_overrides"), name


def test_every_other_mock_of_the_vocabulary_is_rows_of_the_seed_files():
    """The margin, placement and season tests mock only the words they need, each exactly as the seed holds it."""
    tests = _unit_tests()
    words = seed("notice_words")
    for name in SOME_WORDS:
        for row in _given(tests[name], "notice_words"):
            assert row in words, (name, row)
        assert _given(tests[name], "notice_word_overrides") == [], name


def test_no_field_reads_a_word_twice():
    """A word may have two rows only where it matches two ways ('reopened': a whole status not current, a word of a
    title that qualifies its closing word); in any one field it has one reading, or the seed's load order would
    decide which."""
    fields = {}
    for row in seed("notice_words"):
        for field in row["read_in"].split():
            key = (row["word"], field)
            assert key not in fields, (key, fields.get(key), row["reads_as"])
            fields[key] = row["reads_as"]


def test_the_unit_tests_mocked_hazard_seed_is_the_seed_file():
    """The hazard rule (rule 6) is tested on the categories the build reads."""
    for name in (TEST, TEST_HAZARD):
        assert _given(_unit_tests()[name], "notice_hazard_areas") == seed("notice_hazard_areas"), name


def test_no_hazard_seed_row_lists_a_category_that_says_the_hazard_is_absent():
    """A 'No hunting' parcel or a safety zone drawn as a hunting area would tell a hiker the opposite of the layer."""
    for row in seed("notice_hazard_areas"):
        value = row["category_value"].lower()
        assert not value.startswith("no ") and "safety zone" not in value and value != "closed", row


def test_no_rule_of_the_model_names_a_source():
    """What a word means is the same for every source. The model's SQL compares no source_key to a
    literal, and quotes no registered notice source's key; a value no word can read is a row of
    notice_word_overrides, never a branch of the SQL."""
    sql = MODEL.read_text()
    code = "\n".join(line.split("--", 1)[0] for line in sql.splitlines())
    assert not re.search(r"source_key\s*(=|in\b|like\b)\s*\(?\s*'", code)
    readers = (DBT / "seeds" / "notice_readers.csv").read_text()
    # The generated sources, the ones this model reads: a hand-staged key can be a plain word ('closures', OurHike's
    # own), which the model rightly compares as a notice type.
    for row in csv.DictReader(readers.splitlines()):
        if row["staged_by"] != "hand":
            assert f"'{row['source_key']}'" not in code, row["source_key"]


def test_every_override_names_a_staged_field_of_a_registered_notice_source_and_says_why():
    """An override is read exactly, in the one field it names, for its own source alone."""
    fields = {row["source_key"]: row for row in seed("notice_source_fields")}
    for row in seed("notice_word_overrides"):
        assert row["source_key"] in fields, row
        assert fields[row["source_key"]][row["read_in"]], (row, "names a field its source does not stage")
        assert row["why"].strip() and row["reads_as"] in ("not_current", "closes_trail"), row
        assert not reads_as(row["read_in"], row["value"]), (row, "a shared word already reads it")


def test_every_words_row_is_written_as_rule_2_compares_a_value():
    """A `words` row is lowercase letters and digits, one space between, and matches itself: a row the model's
    normalization could never meet (a hyphen, a capital) would read nothing on any source."""
    for row in seed("notice_words"):
        if row["matches"] == "words":
            assert re.fullmatch(r"[a-z0-9]+( [a-z0-9]+)*", row["word"]), row
            assert words_of(row["word"]) == f" {row['word']} ", row
        assert row["why"].strip(), row


def test_nonmotorized_never_reads_as_motorized():
    """'non' joins the word after it, so Michigan's 'Nonmotorized' and 'Multi Use Motorized Nonmotorized', and IDPR's
    'non-motorized use no longer prohibited', never read a non-motorized use as a motorized one."""
    for value in ("Nonmotorized", "Non-Motorized", "non motorized", "marking trail as non-motorized"):
        assert "not_a_hikers_use" not in reads_as("category", value), value
    assert "not_a_hikers_use" in reads_as("category", "Multi Use Motorized Nonmotorized")
    assert "not_a_hikers_use" in reads_as("narrative", "Closed to motorized/mechanized use")


def test_missouris_archived_is_its_only_status_read_as_not_current():
    """P1: "ONLY 'Archived' reads as not current; a blank STATUS shows as current"."""
    assert reads_as("status", "Archived") == {"not_current"}
    assert "not_current" not in reads_as("status", "Caution")
    assert reads_as("status", "Closed") == {"closes_trail"}
    expected = _expected(TEST)
    assert expected["mo_state_parks_trail_advisories:m18"]["held_because"] is None
    assert expected["mo_state_parks_trail_advisories:m18"]["reads_as"] == "notice"


def test_michigans_unspecified_foot_travel_status_is_nothing_for_a_hiker_on_both_layers():
    """P4: '-1', the domain's 'Unspecified', says nothing; the rows' own TrailUseCategory, 'Motorized', limits them to
    a use a hiker is not. It was their category until the review of 2026-10-15 (thread 4279218690) and is read as
    their narrative since, so their category shows their status. A foot-travel status that says closed closes beside
    the same use."""
    assert reads_as("status", "-1") == {"unspecified"}
    assert reads_as("category", "Motorized") == {"not_a_hikers_use"}
    assert reads_as("narrative", "Motorized") == {"not_a_hikers_use"}
    for value in (
        "Temporarily Closed",
        "Temporarily Closed Due To Timber Harvest",
        "Temporarily Closed Due To Water On Trail",
        "Temporarily Closed Due To Trail Washout",
        "Temporarily Closed Due To Bridge Maintenance Or Repair",
        "Temporarily Closed Due To Trail Maintenance Or Repair",
    ):
        assert reads_as("status", value) == {"closes_trail"}, value
    expected = _expected(TEST)
    for notice_id in ("mi_dnr_trail_temporary_closures:d23", "mi_dnr_trail_temporary_reroutes:d25"):
        assert expected[notice_id]["reads_as"] == "nothing_for_a_hiker", notice_id
    decision_190 = _expected(TEST_190)
    for key in ("foot_status_closed", "multi_use_closed"):
        assert decision_190[f"mi_dnr_trail_temporary_closures:{key}"]["obstructs_trail"] is True, key
    assert decision_190["mi_dnr_trail_temporary_reroutes:open_reroute"]["reads_as"] == "notice"


def test_every_closed_value_of_a_florida_parks_day_use_status_closes_and_open_and_no_campground_do_not():
    """P5, frame A: a closed park's trails close with it until its own status reopens it."""
    for reason in (
        "Hurricane/Tropical Storm",
        "Construction/Repair",
        "Fire/Smoke",
        "Flood",
        "Hazardous Materials",
        "Health",
        "Other",
        "Tornado",
    ):
        assert reads_as("status", f"Closed-{reason}") == {"closes_trail"}, reason
    assert reads_as("status", "Open") == {"not_current"}
    assert reads_as("status", "No Campground") == {"not_current"}


def test_a_florida_parks_day_use_point_is_placed_by_its_own_boundary_and_a_campground_by_none():
    """The maintainer's poll of 2026-10-11, "Its own boundary": a park's day-use status point inside exactly one of FDEP's own park
    boundaries takes that boundary as its place (int_closures__club_notices' rule 4), so the trails a closed park
    closes are the ones inside it. A campground's status is about the campground, not the park around it, so the
    campground layer keeps its own points."""
    links = {row["source_key"]: row["areas_source_key"] for row in seed("notice_steward_areas")}
    assert links.get("fl_state_parks_day_use_status") == "fl_state_parks_park_boundaries"
    assert "fl_state_parks_campground_status" not in links


def test_the_gap_alerts_hidden_and_cleared_are_both_not_current_and_fully_obstructed_closes():
    """P6: Hidden (its visibility, staged as the status) and Cleared (its own status, staged as the category)."""
    assert reads_as("status", "Hidden") == {"not_current"}
    assert reads_as("category", "Cleared") == {"not_current"}
    assert readings("category", "Fully Obstructed") == {("closes_trail", "fully obstructed")}
    assert "closes_trail" not in reads_as("category", "Partially Obstructed")
    words = {row["word"]: row for row in seed("notice_words")}
    assert words["fully obstructed"]["outranks_status"] == "false"


def test_netts_damaged_bridges_and_vtranss_active_closure_close_by_their_own_words():
    """With the maintainer's fixes of 2026-10-15, a row closes by its own words: neither layer's own name says
    closures ('NET_KML_DAMAGED_BRIDGES', 'Notice Line'), so each row closes by its own words. NETT's bridges are
    'collapsed' or a 'burned bridge'; VTrans's active row is titled 'Closure', its isActive 1 a flag's yes that says
    nothing of the trail; its isActive 0 holds the row."""
    fields = {row["source_key"]: row for row in seed("notice_source_fields")}
    for key in ("nett_damaged_bridges", "vtrans_rail_trail_closures"):
        assert not layer_closes(fields[key]["layer_title"]), key
    for title in ("Bridge #o - Sulfur River (collapsed)", "Bridge #q - Collapsed Double Arch", "Annona Burned Bridge"):
        assert "closes_trail" in reads_as("title", title), title
    assert "closes_trail" not in reads_as("title", "Culvert collapse under IAT with large hole")
    assert "closes_trail" not in reads_as("title", "BLM issues decision for Burned Area Rehabilitation")
    expected = _expected(TEST)
    assert expected["nett_damaged_bridges:n34"]["read_from"] == "title 'collapsed'"
    assert expected["vtrans_rail_trail_closures:v36"]["read_from"] == "title 'closure'"
    for notice_id in ("nett_damaged_bridges:n34", "vtrans_rail_trail_closures:v36"):
        assert expected[notice_id]["obstructs_trail"] is True, notice_id
    assert expected["vtrans_rail_trail_closures:v35"]["reads_as"] == "not_current"
    assert reads_as("status", "0") == {"not_current"} and reads_as("status", "1") == {"stands"}
    assert reads_as("status", "0", states_only_codes=False) == set(), "a 0 on a scale is never a flag's no"


def test_a_layer_closes_by_its_own_name_only_where_that_name_says_closures():
    """The maintainer's first fix of 2026-10-15: "By their own words" means the source's own layer name, never the
    fact that OurHike files the source under closures. Each name is the layer document's own, read 2026-10-15 and
    recorded as schema (seeds/notice_source_fields.csv's layer_title); an identifier's capitals start words."""
    fields = {row["source_key"]: row for row in seed("notice_source_fields")}
    named = {key for key, row in fields.items() if row["layer_title"] and layer_closes(row["layer_title"])}
    for key in (
        "idpr_emergency_route_closures",
        "scc_parks_closed_areas",
        "nps_yose_trail_closures",
        "usfs_r09_superior_closures",
        "usfs_r06_fire_closure_lines",
        "pcta_closure_lines",
        "wsprc_winter_rec_closures",
    ):
        assert key in named, (key, fields[key]["layer_title"])
    for key in ("iata_trail_conditions", "nett_damaged_bridges", "vtrans_rail_trail_closures", "pcta_fires_and_closures"):
        assert key not in named, (key, fields[key]["layer_title"])
    assert layer_name("TemporaryClosure") == "Temporary Closure"
    assert not layer_closes("Partial Closures"), "a name its own partly word qualifies says no row is a closure"
    sql = MODEL.read_text()
    assert "notice_type = 'closures'\n                and not title_says_not_a_closure" not in sql
    expected = _expected(TEST_190)
    assert expected["fixture_closed_areas:layer_named_closed"]["read_from"] == "layer 'closure'"
    assert expected["fixture_survey_points:layer_named_survey"]["reads_as"] == "notice"


def test_a_closed_site_is_a_notice_and_a_row_that_names_a_trail_is_the_trail():
    """The maintainer's second fix of 2026-10-15: a site's own type is read wherever the source states it, its
    title's last-named thing, its type (USFS's recreation sites' markeractivity, staged as site_type, never as the
    category), its category or its layer's own name; a row whose title or type names a trail is the
    trail."""
    (rec,) = [row for row in seed("notice_source_fields") if row["source_key"] == "usfs_rec_opportunities_status"]
    assert (rec["site_type"], rec["category"]) == ("markeractivity", "openstatus")
    words = {row["word"]: row for row in seed("notice_words")}
    for word in ("campground", "yurt", "sno park", "ski area", "canoe landing", "lake site", "carry down", "camping"):
        assert words[word]["reads_as"] == "a_site_not_the_trail", word
        assert "site_type" in words[word]["read_in"].split(), word
    assert "layer" not in words["day use"]["read_in"].split(), "Florida's 'Day Use Status' is the park's own status"
    assert "title" not in words["recreation site"]["read_in"].split()
    expected = _expected(TEST_190)
    for key in ("rec_campground", "rec_viewing"):
        assert expected[f"fixture_rec_sites:{key}"]["reads_as"] == "notice", key
    for key in ("rec_trail_named", "rec_day_hiking"):
        assert expected[f"fixture_rec_sites:{key}"]["obstructs_trail"] is True, key
    assert expected["fixture_campground_status:campground_layer"]["reads_as"] == "notice"
    assert expected["fixture_trail_status:horse_camp_trail"]["obstructs_trail"] is True
    assert expected["fixture_trail_status:trail_parking"]["reads_as"] == "notice"
    assert expected["idpr_area_restrictions:campground_area"]["obstructs_trail"] is True, "an order that bars entry"
    assert _expected(TEST)["fl_state_parks_campground_status:f29"]["reads_as"] == "notice"


def test_a_closure_that_names_only_roads_closes_the_road_and_no_trail_around_it():
    """The maintainer's third fix of 2026-10-15: an area whose words name a road and no area, trail or entry is a
    notice; 'Area and Road Closures' names the area and closes; a line that names a road closes its own line."""
    assert reads_as("title", "Seasonal Road Closures on the Evanston/Mt. View Ranger Districts") >= {"names_a_road"}
    assert "names_an_area" in reads_as("title", "Area and Road Closures on the Heber-Kamas Ranger District")
    expected = _expected(TEST_190)
    assert expected["fixture_orders:road_only_area"]["reads_as"] == "notice"
    assert expected["fixture_orders:road_only_area"]["read_from"].endswith("an area that names only a road")
    assert expected["fixture_orders:area_and_road"]["obstructs_trail"] is True
    assert expected["idpr_emergency_route_closures:road_line"]["obstructs_trail"] is True


def test_ngpcs_impassable_sections_close_however_road_status_reads():
    """NGPC's settlement (its sources.json row): Condition 'Impassable' or 'Not Passable' closes the trail however
    Road_Status reads, so the Niobrara Bridge section, 'Open' beside 'Not Passable', is never shown as open."""
    words = {row["word"]: row for row in seed("notice_words")}
    for word in ("impassable", "not passable"):
        assert (words[word]["reads_as"], words[word]["outranks_status"]) == ("closes_trail", "true"), word
    assert reads_as("category", "Passable") == set()
    test = _unit_tests()[TEST]
    expected = _expected(TEST)
    niobrara = [
        row
        for row in _given(test, "int_closures__club_notices_unioned")
        if row["source_key"] == "ngpc_cowboy_trail_improvements" and (row["status"], row["category"]) == ("Open", "Not Passable")
    ]
    assert niobrara, "the unit test has no section reading Open beside Not Passable"
    for row in niobrara:
        out = expected[f"ngpc_cowboy_trail_improvements:{row['source_id']}"]
        assert out["obstructs_trail"] is True and out["held_because"] is None, out


def test_a_categorys_closure_is_a_kind_of_notice_that_closes_only_beside_its_title():
    """'closure' in a category is the kind of notice the source files the row as: USFS's forest orders are typed
    'Safety Closure' whatever they bar, 'Forest Wide - Alcohol' among them (read live 2026-10-14). It is the one
    closing word that needs its title, the plural 'closures' agrees with it in a title (and names a layer's closures,
    never a category's topic), and a state ('closed', 'impassable', an exclusion) still closes from a category by
    itself. So does 'Closure' as a placed row's whole category (rule 1): CDTC's alerts so typed and
    titled by place. 'restriction' is the other kind (rule 2), which keeps no title from speaking."""
    words = {row["word"]: row for row in seed("notice_words")}
    kinds = [word for word, row in words.items() if row["category_needs_title"] == "true"]
    assert kinds == ["closure", "restriction", "restrictions"]
    assert [word for word in kinds if words[word]["reads_as"] == "closes_trail"] == ["closure"]
    assert (words["closures"]["read_in"].split(), words["closures"]["reads_as"]) == (["title", "layer"], "closes_trail")
    assert reads_as("category", "Closures and NTH North") == set()
    expected = _expected(TEST_190)
    assert expected["fixture_orders:order_act"]["reads_as"] == "notice"
    assert expected["fixture_orders:order_restriction"]["reads_as"] == "notice"
    assert expected["fixture_club_alerts:club_kind"]["obstructs_trail"] is True
    assert expected["fixture_orders:order_trail_closures"]["obstructs_trail"] is True
    for notice_id in ("idpr_area_restrictions:public_use", "fixture_layer_b:impassable_open"):
        assert expected[notice_id]["obstructs_trail"] is True, notice_id
        assert expected[notice_id]["read_from"].startswith("category '"), notice_id


def test_idprs_named_orders_read_by_their_own_words():
    """IDPR 2232 (any use, beside a note calling the trail non-motorized), 3018 (weekdays) and 2245 (possibly
    closed) close; the three motorized-only shapes are nothing for a hiker; a foot-only basin and a seasonal parking
    restriction stay notices; a fire closure barring public entry beside an OHV ban closes."""
    expected = _expected(TEST_190)
    routes, areas = "idpr_emergency_route_closures", "idpr_area_restrictions"
    for key in ("evans", "trail32", "porters", "washout"):
        assert expected[f"{routes}:{key}"]["obstructs_trail"] is True, key
    for key in ("lightning", "deadwood", "motorvehicles"):
        assert expected[f"{routes}:{key}"]["reads_as"] == "nothing_for_a_hiker", key
    for key in ("public_use", "campground_area", "fire_ohv"):
        assert expected[f"{areas}:{key}"]["obstructs_trail"] is True, key
    for key in ("off_route", "ohv"):
        assert expected[f"{areas}:{key}"]["reads_as"] == "nothing_for_a_hiker", key
    for key in ("foot_only", "seasonal"):
        assert expected[f"{areas}:{key}"]["reads_as"] == "notice", key


def test_a_status_no_word_reads_says_nothing_and_a_flags_coded_unknown_leaves_it_a_flag():
    """The review of 2026-10-15, S1-1 and S2-1: King County's AlertType 'Hazard' and FLTC's workflow 'Final' hold no
    word of the vocabulary, so the row's own title speaks, as the "else a placed row's title" reads, and an
    empty status beside a stated one says nothing either; a status that holds a word still speaks. A flag's coded
    unknown (-1) is read as no status, so it never turns its source's 0 and 1 into a scale."""
    assert reads_as("status", "Hazard") == reads_as("status", "Final") == set()
    assert reads_as("status", "-1") == {"unspecified"}
    expected = _expected(TEST_REVIEW)
    for notice_id in (
        "king_county_parks_alerts_lines:hazard_closed",
        "king_county_parks_alerts_lines:hazard_closure",
        "fltc_temporary_notices:blank_status",
        "fltc_temporary_notices:workflow_status",
        "vtrans_rail_trail_closures:flag_yes",
    ):
        assert expected[notice_id]["obstructs_trail"] is True, notice_id
    assert expected["king_county_parks_alerts_lines:detour_status"]["reads_as"] == "notice"
    assert expected["vtrans_rail_trail_closures:flag_no"]["reads_as"] == "not_current"
    for notice_id in ("fltc_temporary_notices:previous_closure", "fltc_temporary_notices:hiker_notice"):
        assert expected[notice_id]["reads_as"] == "notice", notice_id


def test_a_title_names_each_thing_it_lists_and_a_trail_among_them_is_the_trail():
    """The review of 2026-10-15, S1-2: IATA's 'Trail & Parking Area Closure' lists a trail and a parking area, so it
    closes the trail; 'Trail Parking Lot Closed' and 'Luzerne Horse Trail Campground and Trailhead' name only sites.
    'trl' names a trail, so a USFS 'Nature Trl' typed 'Viewing Scenery' is the trail."""
    words = {(row["word"], row["matches"]): row for row in seed("notice_words")}
    assert words[("trl", "words")]["reads_as"] == "names_a_trail"
    expected = _expected(TEST_REVIEW)
    for key in ("iata_trail_conditions:listed_trail", "usfs_rec_opportunities_status:trl"):
        assert expected[key]["obstructs_trail"] is True, key
    for key in ("iata_trail_conditions:one_site", "usfs_rec_opportunities_status:listed_sites"):
        assert expected[key]["read_from"].endswith("a site and not the trail"), key


def test_a_start_a_title_states_with_a_day_closes_from_that_day():
    """The review of 2026-10-15, S1-4: IATA's 'Hunting Closure beginning 9/1' and 'beginning 10/15' close from their
    day (macros/notice_title_start_day.sql), their narrative saying the trail section is closed (an activity's
    closure alone closes no trail), where a start stated with no day ('Beginning Fall 2027') still keeps the
    title a notice. A park's water systems are a site, so Wisconsin's 'Water Systems Closed (Beginning Oct. 13,
    2026)' stays a notice once its start no longer does it."""
    words = {(row["word"], row["matches"]): row for row in seed("notice_words")}
    for word in ("beginning", "starting", "starts"):
        assert words[(word, "words")]["reads_as"] == "states_a_start", word
    assert words[("water systems", "words")]["reads_as"] == "a_site_not_the_trail"
    expected = _expected(TEST_REVIEW)
    assert expected["iata_trail_conditions:begun"]["starts_on"] == "2026-09-01"
    assert expected["iata_trail_conditions:upcoming"]["starts_on"] == "2026-11-02"
    for key in ("iata_trail_conditions:begun", "iata_trail_conditions:upcoming"):
        assert expected[key]["obstructs_trail"] is True, key
    assert expected["wi_dnr_park_closures:no_day"]["reads_as"] == "notice"
    assert expected["wi_dnr_park_closures:water_systems"]["read_from"].startswith("title 'water systems'")


def test_a_phrase_naming_both_uses_or_everyone_bars_every_use_and_nonmotorized_alone_does_not():
    """The review of 2026-10-15, S2-2: 'motorized and non-motorized use', 'closed to all users' and 'closed to the
    public' bar every use beside a motor vehicle. The bare 'non-motorized' is no hiker's use: IDPR's Lightning Creek
    419 order says 'non-motorized use no longer prohibited' (read live 2026-10-15), which must stay nothing for a
    hiker."""
    for value in (
        "This order closes the trail to motorized and non-motorized use.",
        "The trail is closed to all users due to a washout.",
        "Trail closed to the public. Snowmobile route remains groomed for permit holders.",
    ):
        assert "bars_every_use" in reads_as("narrative", value), value
    no_longer = "Replaced an earlier order: non-motorized use no longer prohibited."
    assert reads_as("narrative", no_longer) & {"bars_every_use", "a_hikers_use"} == set()
    expected = _expected(TEST_REVIEW)
    for key in ("both_uses", "all_users", "the_public"):
        assert expected[f"idpr_emergency_route_closures:{key}"]["obstructs_trail"] is True, key
    assert expected["idpr_emergency_route_closures:no_longer_prohibited"]["reads_as"] == "nothing_for_a_hiker"


def test_a_qualifying_word_inside_a_not_a_qualifier_phrase_qualifies_nothing():
    """The review of 2026-10-15, S2-3: 'closed until further notice', 'no detour available' and 'emergency access
    only' close, where 'notice', 'detour' and 'only' elsewhere still qualify a closing word beside them."""
    assert reads_as("title", "Mist Trail closed until further notice") == {"closes_trail", "names_a_trail"}
    assert "a_way_around" not in reads_as("title", "Bridge out, trail closed, no detour available")
    assert "not_a_closure" not in reads_as("title", "Snow Creek Trail closed, emergency access only")
    assert "not_a_closure" in reads_as("title", "Hiker Notice: Bardeen Rd vehicular closure")
    assert "a_way_around" in reads_as("title", "Trail closed, detour in place")
    expected = _expected(TEST_REVIEW)
    for key in (
        "nps_yose_trail_closures:further_notice",
        "nps_yose_trail_closures:emergency_only",
        "iata_trail_conditions:no_detour",
    ):
        assert expected[key]["obstructs_trail"] is True, key
    assert expected["iata_trail_conditions:detour"]["reads_as"] == "notice"


def test_a_closures_layer_does_not_close_its_detours_or_its_reopenings():
    """The review of 2026-10-15, S2-4: a title naming a way around is the way around, and one that says reopened
    names no current closure, so PCTA's 'Closure Line' layer stops crossing out 'Rattlesnake Flats detour' and 'PCT
    Reopened' and still closes 'Lionshead Fire'."""
    words = {(row["word"], row["matches"]): row for row in seed("notice_words")}
    assert {words[(word, "words")]["reads_as"] for word in ("detour", "reroute")} == {"a_way_around"}
    assert words[("reopened", "words")]["reads_as"] == "not_a_closure"
    assert words[("reopened", "exact")]["reads_as"] == "not_current"
    expected = _expected(TEST_REVIEW)
    for key in ("pcta_closure_lines:detour_line", "pcta_closure_lines:reopened_line", "nps_yose_trail_closures:reopened_title"):
        assert expected[key]["reads_as"] == "notice", key
    assert expected["pcta_closure_lines:closed_line"]["read_from"] == "layer 'closure'"


def test_a_season_is_read_in_the_season_that_has_not_ended_and_contradicting_dates_close_nothing():
    """The review of 2026-10-15, S1-3 and S2-5: a row whose season field states a range of days with no year is read,
    once its own end has passed, in the season that has not ended (pipeline/ELT.md, status rule 4: "neither infinite
    nor last year's date"); COTREX is the one source that names such a field (seeds/notice_source_fields.csv). An end
    before its own start, or a date before 1900, closes no trail."""
    named = {row["source_key"] for row in seed("notice_source_fields") if row["season"]}
    assert named == {"cotrex_seasonal_closures"}
    expected = _expected(TEST_SEASON)
    assert (
        expected["cotrex_seasonal_closures:in_season"]["starts_on"],
        expected["cotrex_seasonal_closures:in_season"]["ends_on"],
    ) == ("2026-10-01", "2027-06-30")
    assert expected["cotrex_seasonal_closures:wraps_the_year"]["ends_on"] == "2027-03-14"
    for key in ("in_season", "next_season", "wraps_the_year", "after_a_label"):
        assert expected[f"cotrex_seasonal_closures:{key}"]["obstructs_trail"] is True, key
    for key in ("misspelt_month", "range_with_years"):
        assert expected[f"cotrex_seasonal_closures:{key}"]["obstructs_trail"] is None, key
    for notice_id in ("idpr_area_restrictions:end_before_start", "nps_yell_bear_management_areas:start_before_1900"):
        assert expected[notice_id]["obstructs_trail"] is None, notice_id


def test_a_facility_the_review_named_is_a_site_and_the_site_words_say_they_are_a_deny_list():
    """The review of 2026-10-15, thread 4279221884: Grand Canyon's 'RV Dump Station', 'Gas Station' and 'North Rim
    Administrative Area', King County's playground, Wisconsin's 'Wildlife Exhibit Area', Region 4's 'Pine Valley CG'
    and USFS's district office, put-in, wayside, hunt camp and resort were crossed out as trails because no site word
    named them. Each word reads as a site in a title; 'administrative' alone does not, so an area closed for
    administrative reasons still closes; and the site rule's own `why` says the words are a deny-list,
    @unvalidated for a facility none of them names."""
    for word in (
        "dump station",
        "gas station",
        "playground",
        "pullout",
        "administrative area",
        "administrative site",
        "housing",
        "exhibit",
        "district office",
        "resort",
        "put in",
        "wayside",
        "hunt camp",
        "cg",
    ):
        assert "a_site_not_the_trail" in reads_as("title", word), word
    assert "a_site_not_the_trail" in reads_as("title", "Cherry Creek Put-in")
    assert "a_site_not_the_trail" not in reads_as("title", "Bright Angel Point Administrative Closure")
    (campground,) = [row for row in seed("notice_words") if row["word"] == "campground"]
    assert "deny-list" in campground["why"] and "@unvalidated" in campground["why"]
    expected = _expected(TEST_FACILITIES)
    for key in (
        "nps_grca_closures:dump_station",
        "nps_grca_closures:administrative_area",
        "usfs_r04_forest_orders:cg_order",
        "usfs_rec_opportunities_status:district_office",
    ):
        assert expected[key]["read_from"].endswith("a site and not the trail"), key
        assert expected[key]["obstructs_trail"] is None, key
    for key in ("nps_grca_closures:administrative_closure", "usfs_rec_opportunities_status:hunt_camp_trail"):
        assert expected[key]["obstructs_trail"] is True, key


def test_every_mock_of_the_category_labels_is_rows_of_the_seed_file():
    """Every reading test mocks seeds/notice_category_labels.csv, empty or with rows exactly as the seed holds them."""
    labels = seed("notice_category_labels")
    for name, test in _unit_tests().items():
        if test["model"] != "int_closures__club_notices":
            continue
        for row in _given(test, "notice_category_labels"):
            assert row in labels, (name, row)


def test_a_category_shows_its_layers_own_label_and_a_bare_identifier_is_named_by_it():
    """The review of 2026-10-15, threads 4279218690 and 4279219442: a category shows as its layer's own label for its
    code (Utah FFSL's 'Prevention Order' is 'Fire Prevention Order'), and a title that is only an identifier is named by
    that label, 'Fire Prevention Order UT914-25-001'. One with no category, a category of no letters, or a category
    that is its status again (Region 8's burn block 'HS84-1'), keeps its identifier; a title of words holding a number
    is its own."""
    labels = {(row["source_key"], row["code"]): row["label"] for row in seed("notice_category_labels")}
    assert labels[("utah_ffsl_fire_restrictions", "Prevention Order")] == "Fire Prevention Order"
    assert labels[("wi_dnr_park_closures", "storm damage")] == "Storm damage"
    expected = _expected(TEST_SHOWN)
    assert expected["utah_ffsl_fire_restrictions:prevention_order"]["title"] == "Fire Prevention Order UT914-25-001"
    assert expected["iata_lands_hunting_regs:open_hunting"]["category"] == "Open for public hunting"
    for key, title in (
        ("fltc_hunting_bypasses:bypass", "M08HBP01"),
        ("wa_dnr_ifpl:precaution_zone", "685"),
        ("usfs_r04_forest_orders:road_order", "NFSR 220 Road Closure"),
        ("usfs_r08_prescribed_burns:burn_block", "HS84-1"),
    ):
        assert expected[key]["title"] == title, key


def test_a_hazard_category_names_its_hazard_by_its_code_its_label_or_its_words_and_never_beside_a_negating_word():
    """Rule 6, one standard for every hazard source (2026-10-15). IATA's layer stages Hunting_Reg's codes ('Open') and
    the hazard seed lists its domain's labels, which seeds/notice_category_labels.csv decodes, so every IATA value the
    seed lists is a label of a code it stages; NY Parks' Description is free text holding the listed 'Hunting area'
    among other words. A value that holds a listed one beside 'no', 'not', 'prohibited' or 'closed' stays held, where
    a listed value read whole is the seed's own reading (USACE's 'Closed to Center-fire Rifles Only / ...')."""
    labels = {(row["source_key"], row["label"]) for row in seed("notice_category_labels")}
    iata = [row for row in seed("notice_hazard_areas") if row["source_key"] == "iata_lands_hunting_regs"]
    assert iata and all((row["source_key"], row["category_value"]) in labels for row in iata)
    expected = _expected(TEST_HAZARD)
    drawn = (
        "iata_lands_hunting_regs:iata_open",
        "iata_lands_hunting_regs:iata_permit",
        "iata_lands_hunting_regs:iata_private",
        "oprhp_hunting_areas:deer",
        "oprhp_hunting_areas:gun_zone",
        "oprhp_hunting_areas:opens",
        "usace_garrison_hunting_restrictions:open_spaced",
        "usace_garrison_hunting_restrictions:rifles",
        "blm_shooting_points:range",
    )
    for key in drawn:
        assert expected[key]["held_because"] is None, key
    assert expected["iata_lands_hunting_regs:iata_open"]["category"] == "Open for public hunting"
    for key, word in (("no_hunting_area", "no"), ("prohibited", "prohibited"), ("closed_to", "closed"), ("not_permitted", "not")):
        assert expected[f"oprhp_hunting_areas:{key}"]["held_because"].endswith(f"beside '{word}', which negates it"), key
    for key in (
        "iata_lands_hunting_regs:iata_closed",
        "oprhp_hunting_areas:safety_zone",
        "oprhp_hunting_areas:no_hunting",
        "oprhp_hunting_areas:non_hunting",
        "oprhp_hunting_areas:plural",
        "usace_garrison_hunting_restrictions:no_hunting_allowed",
    ):
        assert expected[key]["held_because"].endswith("is not one notice_hazard_areas reads as hunting"), key


DECISION_213 = "int_closures__club_notices_reads_decision_213s_rules_for_every_source"


def test_an_activitys_closure_closes_the_trail_only_where_the_rows_narrative_closes_it_too():
    """The maintainer's poll of 2026-10-15, "Activity closures don't close": a closing word right after an activity
    word closes the activity, so USFS R04's 'Butterfly Collection Closure Area' is a notice, where IATA's 'Hunting
    Closure beginning 9/1' still closes beside its narrative's 'The Trail section … is closed' (rule 15). 'fire' is
    no activity: 806 titles name the fire a closure is for. 'camping' is read as a site already."""
    words = {(row["word"], row["matches"]): row for row in seed("notice_words")}
    for word in ("collection", "collecting", "fires", "hunting", "shooting"):
        assert words[(word, "words")]["reads_as"] == "names_an_activity", word
    assert ("fire", "words") not in words
    assert words[("camping", "words")]["reads_as"] == "a_site_not_the_trail"
    for word in ("closed", "closure"):
        assert "narrative" in words[(word, "words")]["read_in"].split(), word
    expected = _expected(DECISION_213)
    assert expected["fixture_orders:activity_order"]["reads_as"] == "notice"
    assert expected["fixture_trail_conditions:activity_trail_closed"]["obstructs_trail"] is True
    assert expected["fixture_trail_conditions:activity_unsaid"]["reads_as"] == "notice"


def test_a_warnings_filed_row_that_names_only_a_road_stays_a_notice():
    """The poll of 2026-10-15, "Roads stay notices": the rule 8 never crosses out a road event. NPS's road
    lines say 'all-lanes-closed' in their status, read as a road; a closures-filed road line still closes."""
    assert "names_a_road" in reads_as("status", "all-lanes-closed")
    expected = _expected(DECISION_213)
    for key in ("warning_road", "warning_lanes"):
        assert expected[f"fixture_road_events:{key}"]["read_from"].endswith("a road and not the trail"), key
    assert expected["fixture_route_orders:worded_issuer"]["obstructs_trail"] is True
