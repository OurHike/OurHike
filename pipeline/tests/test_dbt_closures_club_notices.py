"""int_closures__club_notices reads every notice by its own words against one vocabulary (decision 190).

The maintainer, poll of 2026-10-14: "Do by their own words. But make this logic that applies everywhere. we need to
stop doing org by org customization." seeds/notice_words.csv is that vocabulary, and seeds/notice_word_overrides.csv
the one value no shared word can read. The model's unit tests mock both; this holds each mock to its file, so a test
cannot pass on a vocabulary the build does not use, and holds that no rule of the model names a source.

It also holds the maintainer's answers of 2026-10-11 on how wave 6's statuses read (pages 01 and 02 of that review)
to the shared words, where a later edit would otherwise move one without a word: Missouri's Archived alone is not
current (P1), Michigan's '-1' rows are nothing for a hiker by their own category, 'Motorized' (P4), a closed Florida
park closes its trails (P5) and is placed by its own boundary (Q3, seeds/notice_steward_areas.csv), the Great
Allegheny Passage's Hidden and Cleared are both not current (P6), and NETT's damaged bridges close by their own
words (P11). NGPC's sections read as their sources.json row settles: a Condition of 'Impassable' or 'Not
Passable' closes the trail however Road_Status reads. And decision 190's own cases, by IDPR's live rows of
2026-10-14: an order barring any use closes beside a note calling the trail non-motorized (2232), one barring the
trail on weekdays closes (3018), one possibly closed closes (2245), and the three barring motorized use alone are
nothing for a hiker. A category's 'closure' is the kind of notice, and closes only beside a title that names a
closure too: USFS's forest orders are typed 'Safety Closure' whatever they bar, 'Forest Wide - Alcohol' among them.
And the maintainer's three fixes (poll of 2026-10-15, "Add the 3 fixes"): a layer closes by its own name only where
that name says closures, a closed site is not a closed trail, and an area that names only roads closes no trail.
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
TESTS = (
    TEST,
    TEST_190,
    "int_closures__club_notices_keeps_a_notice_for_a_days_margin_either_side_of_its_own_dates",
    "int_closures__club_notices_places_a_point_inside_exactly_one_of_its_stewards_own_areas_by_that_area",
)


def _unit_tests() -> dict:
    return {test["name"]: test for test in yaml.safe_load(CLOSURES.read_text())["unit_tests"]}


def _given(test: dict, ref: str) -> list[dict]:
    (given,) = [g for g in test["given"] if g["input"] == f"ref('{ref}')"]
    return given["rows"]


def _expected(name: str) -> dict[str, dict]:
    return {row["notice_id"]: row for row in _unit_tests()[name]["expect"]["rows"]}


def test_the_two_reading_tests_mock_the_whole_vocabulary_as_the_seed_files_hold_it():
    tests = _unit_tests()
    for name in (TEST, TEST_190):
        assert _given(tests[name], "notice_words") == seed("notice_words"), name
        assert _given(tests[name], "notice_word_overrides") == seed("notice_word_overrides"), name


def test_every_other_mock_of_the_vocabulary_is_rows_of_the_seed_files():
    """The margin and placement tests mock only the words they need, each exactly as the seed holds it."""
    tests = _unit_tests()
    words = {row["word"]: row for row in seed("notice_words")}
    for name in TESTS[2:]:
        for row in _given(tests[name], "notice_words"):
            assert row == words[row["word"]], (name, row)
        assert _given(tests[name], "notice_word_overrides") == [], name


def test_the_unit_tests_mocked_hazard_seed_is_the_seed_file():
    """Decision 67's hazard rule (rule 6) is tested on the categories the build reads."""
    assert _given(_unit_tests()[TEST], "notice_hazard_areas") == seed("notice_hazard_areas")


def test_no_hazard_seed_row_lists_a_category_that_says_the_hazard_is_absent():
    """A 'No hunting' parcel or a safety zone drawn as a hunting area would tell a hiker the opposite of the layer."""
    for row in seed("notice_hazard_areas"):
        value = row["category_value"].lower()
        assert not value.startswith("no ") and "safety zone" not in value and value != "closed", row


def test_no_rule_of_the_model_names_a_source():
    """Decision 190: what a word means is the same for every source. The model's SQL compares no source_key to a
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
    """P1: "ONLY 'Archived' reads as not current; a blank STATUS shows as current" (decision 164)."""
    assert reads_as("status", "Archived") == {"not_current"}
    assert "not_current" not in reads_as("status", "Caution")
    assert reads_as("status", "Closed") == {"closes_trail"}
    expected = _expected(TEST)
    assert expected["mo_state_parks_trail_advisories:m18"]["held_because"] is None
    assert expected["mo_state_parks_trail_advisories:m18"]["reads_as"] == "notice"


def test_michigans_unspecified_foot_travel_status_is_nothing_for_a_hiker_on_both_layers():
    """P4: '-1', the domain's 'Unspecified', says nothing; the rows' own category, 'Motorized', limits them to a use
    a hiker is not. A foot-travel status that says closed closes beside the same category."""
    assert reads_as("status", "-1") == {"unspecified"}
    assert reads_as("category", "Motorized") == {"not_a_hikers_use"}
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
    """Q3 (poll of 2026-10-11, "Its own boundary"): a park's day-use status point inside exactly one of FDEP's own park
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
    """P11, frame A, and decision 190 with the maintainer's fixes of 2026-10-15: neither layer's own name says
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
    category, decision 78), its category or its layer's own name; a row whose title or type names a trail is the
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
    'Safety Closure' whatever they bar, 'Forest Wide - Alcohol' among them (read live 2026-10-14). It is the one word
    that needs its title, the plural 'closures' agrees with it in a title (and names a layer's closures, never a
    category's topic), and a state ('closed', 'impassable',
    an exclusion) still closes from a category by itself."""
    words = {row["word"]: row for row in seed("notice_words")}
    assert [word for word, row in words.items() if row["category_needs_title"] == "true"] == ["closure"]
    assert (words["closures"]["read_in"].split(), words["closures"]["reads_as"]) == (["title", "layer"], "closes_trail")
    assert reads_as("category", "Closures and NTH North") == set()
    expected = _expected(TEST_190)
    assert expected["fixture_orders:order_act"]["reads_as"] == "notice"
    assert expected["fixture_orders:order_restriction"]["reads_as"] == "notice"
    assert expected["fixture_club_alerts:club_kind"]["reads_as"] == "notice"
    assert expected["fixture_orders:order_trail_closures"]["obstructs_trail"] is True
    for notice_id in ("idpr_area_restrictions:public_use", "fixture_layer_b:impassable_open"):
        assert expected[notice_id]["obstructs_trail"] is True, notice_id
        assert expected[notice_id]["read_from"].startswith("category '"), notice_id


def test_idprs_named_orders_read_as_the_brief_and_decision_190_say():
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
