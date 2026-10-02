"""The closures and warnings family's SQL refuses and reads what today's Python does, on the same rows (#1793, stage 3).

ATC's reviewed Trail Updates, NYNJTC's Trail Alerts and NWS's relay moved to
SQL (pipeline/ELT.md's ledger, CL01-CL06, WN01-WN08), and until stage 5
deletes the Python both are live. parity.py compares the phone files in CI,
on the real reference/atc_updates.json and on fixture mode's answers for the
rest; this holds what those inputs never exercise, because almost all of it
is a refusal:

- dbt_project.yml's vars are lib/atc_updates.py's constants, and
  python_html_unescape's tables are Python's html module's;
- lib/atc_updates.py's file_problems(), run over int_closures__atc_checked's
  unit-test rows, refuses the same rows in the same words;
- lib/nynjtc_alerts.py's parse_alert(), over int_closures__nynjtc_checked's
  unit-test posts, reads the same titles, localities and dates and refuses
  the same posts;
- export_weather_alerts.py's relayed(), over int_warnings__nws_relayed's
  unit-test alerts, relays the same ones;
- lib/nbm_grid.py's _to_grid_units() puts every vertex of
  int_warnings__nws_alert_shapes' unit-test polygons where the SQL does, to
  the last bit, and export_weather_alerts.py's bake(), over the squares and
  alerts int_warnings__nws_placed's unit tests stand for, places each alert
  on the same squares and reports the same unknown zones (WN03);
- export_atc_updates.py's main(), over the files int_closures__gate's unit
  tests stand for, publishes where the gate passes;
- lib/atc_updates.py's auto_publish_refusal() and auto_row(), over
  int_closures__atc_automatic's unit-test pages, refuse the same updates in
  the same words and write the same rows (CL07-CL10), and
  propose_atc_updates.py's _actionable() keeps the same refusals (CL12);

except where a DELIBERATE set below names a row the SQL treats otherwise on
purpose. Each such row must still differ, so emptying a set turns its test red.
"""

import html
import html.entities
import importlib.util
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pytest
import yaml

import export_atc_updates
import export_weather_alerts
import fetch_nynjtc_alerts
import parity
import propose_atc_updates
from lib import atc_updates, nbm_grid, nynjtc_alerts
from lib.atc_scrape import MileReference, ParsedUpdate

DBT = Path(__file__).parent.parent / "dbt"
CLOSURES = DBT / "models" / "intermediate" / "closures" / "_closures__intermediate.yml"
WARNINGS = DBT / "models" / "intermediate" / "warnings" / "_warnings__intermediate.yml"
UNESCAPE = DBT / "macros" / "python_html_unescape.sql"

# ATC rows the SQL refuses and file_problems() passes: row 36, a source_url
# with a leading space. urlparse() strips it before reading the scheme, and
# the phone would then open the link with the space still in it, so the SQL
# reads the scheme as written, as int_podcasts__checked reads a link.
DELIBERATE_ATC_ROWS = {36}

# NYNJTC posts the SQL reads otherwise, each on purpose:
#   n09  `&frac34;`, a name python_html_unescape does not know, is left as
#        written, where html.unescape() writes "¾" (the macro's header);
#   n14, n15  one slug on two posts: the cache is a dict by slug, so the
#        second silently replaces the first, and the SQL refuses both rather
#        than drop one;
#   n16  a title that is not a string: _text_of() publishes str(5), and the
#        SQL refuses it as a payload whose shape has changed.
DELIBERATE_NYNJTC_POSTS = {"n09", "n14", "n15", "n16"}

# ATC pages the SQL refuses and auto_publish_refusal() publishes: u19, a
# dateModified in ISO 8601's basic form (20260819T162250Z), which Python
# 3.11's fromisoformat() reads and python_fromisoformat_utc() does not, so the
# SQL refuses it as "not since the review". Every live page read on
# 2026-10-02, 86 of 86, wrote YYYY-MM-DDTHH:MM:SS-04:00, which both read.
DELIBERATE_ATC_AUTOMATIC_ROWS = {"u19"}

# The tests of the auto-publish gate in tests/test_lib_atc_updates.py, each
# with the int_closures__atc_automatic unit-test row that stands for it
# (pipeline/ELT.md, "Tests move with their rule").
AUTO_GATE_CASES = {
    "test_an_update_atc_posted_since_the_review_publishes_itself": "u00",
    "test_an_update_older_than_the_review_is_refused": "u01",
    "test_a_reviewed_slug_is_never_overwritten_by_a_parse": "u02-reviewed",
    "test_mile_references_that_disagree_are_refused_rather_than_guessed_between": "u03",
    "test_the_gate_refuses_a_mile_off_the_end_of_the_trail": "u04",
    "test_an_all_clear_publishes_rather_than_being_refused": "u05",
    "test_the_same_mile_stated_twice_is_not_a_disagreement": "u06",
    "test_a_category_this_build_does_not_know_is_refused": "u07",
    "test_an_automatic_row_can_never_draw_a_band": "u00",
    "test_an_automatic_rows_timestamp_is_utc_like_every_reviewed_one": "u00",
}


def _unit_tests(path: Path) -> dict[str, dict]:
    return {test["name"]: test for test in yaml.safe_load(path.read_text())["unit_tests"]}


def _given(test: dict, model: str) -> dict:
    return next(given for given in test["given"] if given["input"] == f"ref('{model}')")


def _same_words(message: str | None) -> str | None:
    """A message with Python's repr and JSON told apart only by quotes, spaces and the names of true and null."""
    if message is None:
        return None
    return re.sub(r"\s+", "", message.replace("'", '"')).replace("True", "true").replace("None", "null")


# --- The constants ------------------------------------------------------------


def test_the_atc_vars_are_lib_atc_updates_constants():
    variables = yaml.safe_load((DBT / "dbt_project.yml").read_text())["vars"]
    assert variables["atc_trail_mile_min"] == atc_updates.TRAIL_MILE_MIN
    assert variables["atc_trail_mile_max"] == atc_updates.TRAIL_MILE_MAX
    assert variables["atc_update_categories"] == sorted(atc_updates.CATEGORIES)


def _macro_map(name: str) -> dict:
    """The keys and values of the one `map([...], [...])` a python_html_unescape helper macro returns."""
    body = re.search(r"\{% macro " + name + r"\(\) -%\}(.*?)\{%- endmacro %\}", UNESCAPE.read_text(), re.S).group(1)
    keys, values = re.findall(r"\[([^\]]*)\]", body)
    return dict(zip(json.loads(f"[{keys.replace(chr(39), chr(34))}]"), json.loads(f"[{values}]"), strict=True))


def test_every_entity_name_the_unescape_knows_is_pythons_spelling_and_character():
    names = _macro_map("_html_names")
    assert names, "no names parsed out of _html_names()"
    for name, code_point in names.items():
        assert html.entities.html5.get(name) == chr(code_point), name


def test_the_replaced_code_points_are_htmls_own_table():
    """html._invalid_charrefs: U+0000, U+000D and U+0080-U+009F, which the HTML5 spec reads otherwise."""
    assert _macro_map("_html_replaced") == {number: ord(text) for number, text in html._invalid_charrefs.items()}


# --- ATC's reviewed rows --------------------------------------------------------


def test_file_problems_refuses_what_the_atc_unit_test_expects():
    test = _unit_tests(CLOSURES)["int_closures__atc_checked_finds_what_file_problems_finds"]
    rows = sorted(_given(test, "base_atc__atc_trail_updates")["rows"], key=lambda row: row["file_row"])
    expected = {row["file_row"]: row["problem"] for row in test["expect"]["rows"]}
    updates = [json.loads(row["atc_update"]) for row in rows]
    assert [row["file_row"] for row in rows] == list(range(len(updates))) and set(expected) == set(range(len(updates)))
    for n in range(len(updates)):
        # file_problems() appends each row's problems in order, so row n's are what its first n + 1 rows add.
        before = atc_updates.file_problems({"updates": updates[:n]})
        python = " | ".join(atc_updates.file_problems({"updates": updates[: n + 1]})[len(before) :]) or None
        if n in DELIBERATE_ATC_ROWS:
            assert python is None and expected[n] is not None, f"row {n} is no longer a deliberate difference"
            continue
        assert _same_words(python) == _same_words(expected[n]), f"row {n}: Python {python!r}, SQL {expected[n]!r}"


def _bake(tmp_path, monkeypatch, document: dict):
    """export_atc_updates.py's main() over one reviewed file: its manifest, None, or the SystemExit it refuses with."""
    reviewed = tmp_path / "atc_updates.json"
    reviewed.write_text(json.dumps(document))
    monkeypatch.setattr(export_atc_updates, "REVIEWED_PATH", reviewed)
    monkeypatch.setattr(export_atc_updates, "OUT_DIR", tmp_path / "conditions")
    monkeypatch.setattr(export_atc_updates, "OUT_PATH", tmp_path / "conditions" / "atc_updates.json")
    monkeypatch.setattr(export_atc_updates, "MANIFEST_PATH", tmp_path / "atc_updates_manifest.json")
    monkeypatch.setattr(export_atc_updates, "CACHE_PATH", tmp_path / "no_cache.json")
    try:
        return export_atc_updates.main()
    except SystemExit as refused:
        return refused


GOOD_ROW = json.loads(
    _given(_unit_tests(CLOSURES)["int_closures__atc_checked_finds_what_file_problems_finds"], "base_atc__atc_trail_updates")[
        "rows"
    ][0]["atc_update"]
)

# The file each of int_closures__gate's ATC unit tests stands for. The gate
# reads the review from the file landed whole (base_atc__atc_updates), so an
# empty reviewed file passes, as export_atc_updates.py publishes it.
GATE_FILES = {
    "int_closures__gate_holds_back_one_bad_atc_row_and_nothing_else": {
        "reviewed_at": "2026-08-24",
        "updates": [GOOD_ROW, {key: value for key, value in GOOD_ROW.items() if key != "obstructs_trail"} | {"atc_id": "a01"}],
    },
    "int_closures__gate_holds_back_an_unreviewed_atc_file": {"reviewed_at": "  ", "updates": [GOOD_ROW]},
    "int_closures__gate_passes_an_empty_reviewed_atc_file_and_holds_back_an_unverified_closure": {
        "reviewed_at": "2026-08-24",
        "updates": [],
    },
    "int_closures__gate_holds_back_an_atc_file_whose_updates_is_not_a_list": {
        "reviewed_at": "2026-08-24",
        "updates": {"a01": GOOD_ROW},
    },
}


@pytest.mark.parametrize("name", sorted(GATE_FILES))
def test_the_gate_holds_back_what_export_atc_updates_does_not_publish(name, tmp_path, monkeypatch):
    test = _unit_tests(CLOSURES)[name]
    (atc,) = [row for row in test["expect"]["rows"] if row["source_key"] == "atc_trail_updates"]
    python_publishes = isinstance(_bake(tmp_path, monkeypatch, GATE_FILES[name]), dict)
    assert python_publishes == atc["passed"], name


# --- ATC's automatic rows (CL07-CL10, CL12) ---------------------------------------

AUTOMATIC = "int_closures__atc_automatic_refuses_what_auto_publish_refusal_refuses"
AUTOMATIC_ROWS = "int_closures__atc_automatic_writes_the_row_auto_row_writes"


def _pages(test: dict) -> tuple[list[ParsedUpdate], set[str], str]:
    """The unit test's base rows as the ParsedUpdates fetch_atc_updates.py would have cached, the reviewed slugs, and reviewed_at."""
    pages = []
    for row in _given(test, "base_atc__atc_trail_updates_pages")["rows"]:
        pages.append(
            ParsedUpdate(
                slug=row["slug"],
                title=row["title"] or "",
                category=row["category"],
                states=json.loads(row["states"]),
                date_modified=row["date_modified"],
                date_published=None,
                miles=[MileReference(m["direction"], m["start"], m["end"], m["raw"]) for m in json.loads(row["miles"])],
                text="",
            )
        )
    reviewed = {row["atc_id"] for row in _given(test, "int_closures__atc_checked")["rows"]}
    (document,) = _given(test, "base_atc__atc_updates")["rows"]
    return pages, reviewed, json.loads(document["document_json"])["reviewed_at"]


def test_every_auto_gate_case_in_test_lib_atc_updates_has_its_unit_test_row():
    source = (Path(__file__).parent / "test_lib_atc_updates.py").read_text()
    slugs = {page.slug for page in _pages(_unit_tests(CLOSURES)[AUTOMATIC])[0]}
    for case, slug in AUTO_GATE_CASES.items():
        assert f"def {case}(" in source, f"{case} is no longer in tests/test_lib_atc_updates.py"
        assert slug in slugs, f"{case}'s row {slug} is no longer in {AUTOMATIC}"


def test_auto_publish_refusal_refuses_what_the_atc_automatic_unit_test_expects():
    test = _unit_tests(CLOSURES)[AUTOMATIC]
    pages, reviewed, reviewed_at = _pages(test)
    expected = {row["slug"]: row for row in test["expect"]["rows"]}
    assert set(expected) == {page.slug for page in pages}
    for page in pages:
        python = atc_updates.auto_publish_refusal(page, reviewed, reviewed_at)
        sql = expected[page.slug]
        if page.slug in DELIBERATE_ATC_AUTOMATIC_ROWS:
            assert python is None and sql["refusal"] is not None, f"{page.slug} is no longer a deliberate difference"
            continue
        assert _same_words(python) == _same_words(sql["refusal"]), f"{page.slug}: Python {python!r}, SQL {sql['refusal']!r}"
        # CL12: the refusals propose_atc_updates.py proposes to a person.
        assert (python is not None and propose_atc_updates._actionable(python)) == sql["actionable"], page.slug


def test_auto_row_writes_what_the_atc_automatic_unit_test_expects():
    """Field by field and type by type: a whole mile stays a float (1138.0), and obstructs_trail is False on every row (CL09)."""
    test = _unit_tests(CLOSURES)[AUTOMATIC_ROWS]
    pages, reviewed, reviewed_at = _pages(test)
    expected = {row["slug"]: row["published_row"] for row in test["expect"]["rows"]}
    published = 0
    for page in pages:
        if page.slug in DELIBERATE_ATC_AUTOMATIC_ROWS:
            assert expected[page.slug] is None
            continue
        if atc_updates.auto_publish_refusal(page, reviewed, reviewed_at) is not None:
            assert expected[page.slug] is None, page.slug
            continue
        python, sql = atc_updates.auto_row(page), json.loads(expected[page.slug])
        assert list(sql) == list(python), "the same fields in auto_row()'s order"
        assert [(type(v), v) for v in sql.values()] == [(type(v), v) for v in python.values()], page.slug
        assert sql["obstructs_trail"] is False
        published += 1
    assert published >= 10, "the unit test should hold every way a row publishes"


# --- NYNJTC's Trail Alerts ------------------------------------------------------


def _wordpress(test: dict) -> tuple[dict[str, dict], dict]:
    """The unit test's base rows as the WordPress posts and vocabularies they were landed from."""
    payloads: dict[str, list] = {taxonomy: [] for taxonomy in nynjtc_alerts.PLACE_TAXONOMIES}
    for term in _given(test, "base_nynjtc__nynjtc_trail_alerts_terms")["rows"]:
        payloads[term["taxonomy"]].append({"id": term["term_id"], "name": term["term_name"], "slug": term["slug"]})
    vocabularies = {taxonomy: nynjtc_alerts.parse_terms(payload) for taxonomy, payload in payloads.items()}
    posts = {}
    for row in _given(test, "base_nynjtc__nynjtc_trail_alerts")["rows"]:
        modified = row["modified_at"]
        posts[row["trail_alert_key"]] = {
            "id": row["post_id"],
            "slug": row["slug"],
            "link": row["link"],
            "title": json.loads(row["title_json"]),
            # dlt read WordPress's offset-free `modified` as UTC, so the landed value is that text read as UTC.
            "modified": modified[:19].replace(" ", "T") if modified is not None else None,
            **{taxonomy: json.loads(row[f"{taxonomy}_term_ids"]) for taxonomy in nynjtc_alerts.PLACE_TAXONOMIES},
        }
    return posts, vocabularies


def test_parse_alert_reads_what_the_nynjtc_unit_test_expects():
    test = _unit_tests(CLOSURES)["int_closures__nynjtc_checked_reads_each_post_as_parse_alert_does"]
    posts, vocabularies = _wordpress(test)
    expected = test["expect"]["rows"]
    assert len(expected) == len(posts)
    now = datetime.now(timezone.utc)
    for (key, post), row in zip(posts.items(), expected, strict=True):
        alert = nynjtc_alerts.parse_alert(post, vocabularies)
        python = None
        if alert is not None:
            entry = fetch_nynjtc_alerts.as_cache_entry(alert, now)
            (python,) = nynjtc_alerts.published_rows({alert.slug: entry})
        agrees = (python is None) == (row["problem"] is not None) and (
            python is None
            or (python["notice_id"], python["title"], python["locality"], python["updated_at"])
            == (row["notice_id"], row["title"], row["locality"], row["updated_at"])
        )
        if key in DELIBERATE_NYNJTC_POSTS:
            assert not agrees, f"{key} is no longer a deliberate difference"
            continue
        assert agrees, f"{key}: Python {python!r}, SQL {row!r}"


# --- NWS's relay ----------------------------------------------------------------

ALERT_VALUES = re.compile(r"\('([^']*)', (null|'[^']*'), (null|'[^']*'), '[^']*'\)")


def test_relayed_relays_what_the_nws_unit_test_expects():
    test = _unit_tests(WARNINGS)["int_warnings__nws_relayed_test_messages_and_cancellations_are_not_relayed"]
    given = ALERT_VALUES.findall(_given(test, "base_nws__alerts")["rows"])
    assert len(given) == 10, "the unit test's VALUES rows were not all read"

    def text(value: str) -> str | None:
        return None if value == "null" else value.strip("'")

    relayed = {
        f"nws_alerts:{alert_id}"
        for alert_id, status, message_type in given
        if export_weather_alerts.relayed({"properties": {"status": text(status), "messageType": text(message_type)}})
    }
    assert relayed == {row["notice_id"] for row in test["expect"]["rows"]}


# --- NWS's placement on the weather squares (WN03) ---------------------------------

PLACED_TESTS = [
    "int_warnings__nws_placed_places_each_alert_as_export_weather_alerts_bake_does",
    "int_warnings__nws_placed_a_shape_reaching_any_part_of_a_square_reaches_it",
    "int_warnings__nws_placed_a_shape_that_only_touches_an_edge_or_corner_does_not_reach",
    "int_warnings__nws_placed_each_shape_gets_its_own_answer",
]
SHAPES_TEST = "int_warnings__nws_alert_shapes_puts_a_drawn_alert_in_nbm_grid_units"
NUMBER = re.compile(r"-?\d+(?:\.\d+)?(?:e-?\d+)?")


def test_the_nbm_grid_vars_are_lib_nbm_grids_constants():
    variables = yaml.safe_load((DBT / "dbt_project.yml").read_text())["vars"]
    assert variables["nbm_grid_proj4"] == nbm_grid.PROJ4
    assert variables["nbm_grid_origin_x"] == nbm_grid.ORIGIN_X
    assert variables["nbm_grid_origin_y"] == nbm_grid.ORIGIN_Y
    assert variables["nbm_grid_square_m"] == nbm_grid.SQUARE_M


def test_nbm_grid_units_puts_every_vertex_where_to_grid_units_does_to_the_last_bit():
    """The shapes unit test's WKT, read back as doubles, is _to_grid_units() of each lon/lat vertex, exactly:
    whether a polygon only touches a square's edge turns on the last bit (macro nbm_grid_units's header)."""
    test = _unit_tests(WARNINGS)[SHAPES_TEST]
    expected = {row["notice_id"]: row["grid_shape_wkt"] for row in test["expect"]["rows"]}
    drawn = 0
    for row in _given(test, "int_warnings__nws_relayed")["rows"]:
        if row["geom_geojson"] is None:
            assert expected[row["notice_id"]] is None
            continue
        (ring,) = json.loads(row["geom_geojson"])["coordinates"]
        python = nbm_grid._to_grid_units(np.array(ring, dtype=float)).ravel().tolist()
        assert [float(number) for number in NUMBER.findall(expected[row["notice_id"]])] == python, row["notice_id"]
        drawn += 1
    assert drawn == 3


def test_the_placed_unit_tests_draw_the_shapes_unit_tests_polygons():
    shapes = {row["grid_shape_wkt"] for row in _unit_tests(WARNINGS)[SHAPES_TEST]["expect"]["rows"]}
    main = _given(_unit_tests(WARNINGS)[PLACED_TESTS[0]], "int_warnings__nws_alert_shapes")["rows"]
    assert {row["grid_shape_wkt"] for row in main if row["is_drawn"]} <= shapes


def test_the_placed_unit_tests_squares_and_zones_are_test_export_weather_alerts_squares():
    spec = importlib.util.spec_from_file_location("weather_alerts_tests", Path(__file__).parent / "test_export_weather_alerts.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    squares = module.SQUARES
    document = _placed_squares(_unit_tests(WARNINGS)[PLACED_TESTS[0]])
    assert sorted(map(tuple, document["cells"]["unit_test"])) == sorted(
        {tuple(square) for cell in squares["cells"].values() for square in cell}
    )
    assert document["zones"] == squares["zones"]
    assert {kind: sorted(ids) for kind, ids in document["known_zones"].items()} == {
        kind: sorted(ids) for kind, ids in squares["known_zones"].items()
    }


def _placed_squares(test: dict) -> dict:
    """The squares.json a placed unit test's weather squares and zones stand for."""
    zones = _given(test, "int_warnings__weather_zones")["rows"]
    known: dict[str, list[str]] = {}
    for row in zones:
        if row["is_known"]:
            known.setdefault(row["zone_key"].split("/", 1)[0], []).append(row["zone_id"])
    return {
        "release": "unit_test",
        "zone_files": {},
        "cells": {
            "unit_test": [[row["square_row"], row["square_col"]] for row in _given(test, "int_warnings__weather_squares")["rows"]]
        },
        "zones": {row["zone_key"]: json.loads(row["squares"]) for row in zones if json.loads(row["squares"])},
        "known_zones": known,
    }


@pytest.mark.parametrize("name", PLACED_TESTS)
def test_bake_places_what_the_placed_unit_test_expects(name, monkeypatch):
    """bake() over the squares and alerts a placed unit test stands for. Its polygons are already in grid units,
    so _to_grid_units is the identity here, as tests/test_lib_nbm_grid.py's grid_units fixture makes it."""
    import shapely

    monkeypatch.setattr(nbm_grid, "_to_grid_units", lambda xy: xy)
    test = _unit_tests(WARNINGS)[name]
    features = [
        {
            "geometry": json.loads(shapely.to_geojson(shapely.from_wkt(row["grid_shape_wkt"]))) if row["is_drawn"] else None,
            "properties": {
                "id": row["alert_id"],
                "status": "Actual",
                "messageType": "Alert",
                "affectedZones": json.loads(row["affected_zones"]),
            },
        }
        for row in _given(test, "int_warnings__nws_alert_shapes")["rows"]
    ]
    now = datetime.now(timezone.utc)
    document = export_weather_alerts.bake(_placed_squares(test), {"type": "FeatureCollection", "features": features}, now, now)
    published = {f"nws_alerts:{alert['id']}": alert for alert in document["alerts"]}
    unknown: set[str] = set()
    for row in test["expect"]["rows"]:
        alert = published.get(row["notice_id"])
        if "reaches_trail" in row:
            assert (alert is not None) == row["reaches_trail"], row["notice_id"]
        if "squares" in row:
            assert (alert["squares"] if alert else []) == json.loads(row["squares"]), row["notice_id"]
        if "placed_by" in row and alert is not None:
            assert alert["placed_by"] == row["placed_by"], row["notice_id"]
        unknown |= set(json.loads(row.get("unknown_zones", "[]")))
    assert set(published) <= {row["notice_id"] for row in test["expect"]["rows"]}
    assert document["unknown_zones"] == sorted(unknown)


def test_the_fixtures_weather_squares_are_where_nbm_grid_puts_their_points():
    """make_dbt_fixtures.py's squares.json lists the squares lib/nbm_grid.py puts its points in, by the cells
    build_weather_squares.py's squares_by_cell() groups them into."""
    import build_weather_squares
    import make_dbt_fixtures

    points = make_dbt_fixtures.WEATHER_SQUARE_POINTS
    lons, lats = (np.array([point[0][axis] for point in points.values()]) for axis in (0, 1))
    rows, cols = nbm_grid.squares(lons, lats)
    assert list(zip(rows.tolist(), cols.tolist(), strict=True)) == [square for _, square in points.values()]
    cells, outside = build_weather_squares.squares_by_cell(lons, lats)
    assert (cells, outside) == (make_dbt_fixtures._weather_squares()["cells"], [])


# --- parity.py's run stamps -------------------------------------------------------


def test_a_run_stamp_is_held_to_its_form_and_not_its_value():
    family = parity.Family(old=dict, records="closures", key="id", stamps=("generated_at",))
    old = {"generated_at": "2026-10-02T03:08:16.614949Z", "closures": []}
    assert parity.differences(old, {**old, "generated_at": "2026-10-02T04:00:00Z"}, family) == []
    assert parity.differences(old, {**old, "generated_at": "2026-10-02T04:00:00+00:00"}, family) != []
    assert parity.differences(old, {"closures": []}, family) != []
