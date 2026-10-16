"""gate_report.py and parity.py --json-dir: the gate's one answer per R2 key, from the shadow run's results."""

import json
from pathlib import Path

import pytest

import gate_report
import parity
from gate_report import DbtKey, TodayKey, key_rows
from parity import Family

A = {"spotify_id": "a", "title": "One", "capacity": 4}
B = {"spotify_id": "b", "title": "Two", "capacity": 6}


def _family(document: dict, **options) -> Family:
    return Family(old=lambda: document, records="episodes", key="spotify_id", ordered=True, **options)


def _run(monkeypatch, tmp_path, old: dict, new: dict, **options) -> tuple[int, dict]:
    monkeypatch.setitem(parity.FAMILIES, "fake", _family(old, **options))
    new_path = tmp_path / "fake_file.json"
    new_path.write_text(json.dumps(new))
    code = parity.main(["fake", "--new", str(new_path), "--json-dir", str(tmp_path / "results")])
    return code, json.loads((tmp_path / "results" / "fake.json").read_text())


# --- parity.py --json-dir -------------------------------------------------------


def test_parity_json_dir_keeps_the_console_and_exit_code_and_writes_the_result(monkeypatch, tmp_path, capsys):
    code, result = _run(monkeypatch, tmp_path, {"episodes": [A, B]}, {"episodes": [A, {**B, "title": "Too"}]})
    assert code == 1
    assert "spotify_id b" in capsys.readouterr().out
    assert result["format"] == parity.RESULT_FORMAT
    assert (result["outcome"], result["exit_code"], result["new_file_name"]) == ("differences", 1, "fake_file.json")
    assert [(d["what"], d["fields"]) for d in result["differences"]] == [("spotify_id b", ["title"])]

    code, result = _run(monkeypatch, tmp_path, {"episodes": [A, B]}, {"episodes": [A, B]})
    assert (code, result["outcome"], result["old_records"], result["new_records"]) == (0, "no_differences", 2, 2)


def test_parity_json_names_every_field_of_a_record_the_new_path_loses(monkeypatch, tmp_path):
    """A lost row reads as losing its fields, so a lost shelter ranks as a capacity difference."""
    _, result = _run(monkeypatch, tmp_path, {"episodes": [A, B]}, {"episodes": [A]})
    lost = next(d for d in result["differences"] if d["what"] == "spotify_id b")
    assert lost["fields"] == ["capacity", "spotify_id", "title"]
    assert next(d for d in result["differences"] if d["what"] == "order")["fields"] == ["order"]


def test_parity_json_names_the_record_an_exact_copy_copies_and_the_fields_they_differ_on(monkeypatch, tmp_path):
    """The exact-copy standard's two facts (result_document()): the record on the other side an exact copy copies, and the field
    paths the two differ on. Here the copy differs from its partner in its key alone, then in a capacity the dbt
    writer changed too. A difference no exact-copy reason explains, and a partner its side lacks, get neither, and
    --keys-only keeps both facts while it drops every record."""
    explained = {
        "spotify_id b2": parity.POI_REASONS["exact_copy"],
        "spotify_id a2": "expected by a test, as no copy",
        "spotify_id b3": parity.POI_REASONS["exact_copy"],
    }
    options = {
        "explained": lambda old, new: explained,
        "copies": lambda old, new: {"spotify_id b2": "b", "spotify_id a2": "a", "spotify_id b3": "gone"},
    }
    old = {"episodes": [A, B, {**B, "spotify_id": "b2"}, {**A, "spotify_id": "a2"}, {**B, "spotify_id": "b3"}]}

    _, result = _run(monkeypatch, tmp_path, old, {"episodes": [A, B]}, **options)
    by_what = {item["what"]: item for item in result["explained"]}
    assert (by_what["spotify_id b2"]["exact_copy_of"], by_what["spotify_id b2"]["differs_from_exact_copy"]) == (
        "spotify_id b",
        ["spotify_id"],
    )
    assert "exact_copy_of" not in by_what["spotify_id a2"] and "exact_copy_of" not in by_what["spotify_id b3"]

    _, result = _run(monkeypatch, tmp_path, old, {"episodes": [A, {**B, "capacity": 7}]}, **options)
    copy = next(item for item in result["explained"] if item["what"] == "spotify_id b2")
    assert copy["differs_from_exact_copy"] == ["capacity", "spotify_id"]
    kept = parity.without_records(result)["explained"]
    assert next(item for item in kept if item["what"] == "spotify_id b2")["differs_from_exact_copy"] == ["capacity", "spotify_id"]
    assert all("old" not in item and "new" not in item for item in kept)


def test_parity_json_writes_an_old_side_refusal_before_the_same_exit(monkeypatch, tmp_path):
    def refuses():
        raise SystemExit("export_fake.py refuses its input, so it would publish nothing")

    monkeypatch.setitem(parity.FAMILIES, "fake", Family(old=refuses, records="episodes", key="spotify_id"))
    (tmp_path / "new.json").write_text("{}")
    with pytest.raises(SystemExit, match="refuses its input"):
        parity.main(["fake", "--new", str(tmp_path / "new.json"), "--json-dir", str(tmp_path)])
    result = json.loads((tmp_path / "fake.json").read_text())
    assert (result["outcome"], result["exit_code"]) == ("old_side_refused", 1)
    assert "refuses its input" in result["message"]


def test_parity_json_without_the_flag_writes_nothing(monkeypatch, tmp_path):
    monkeypatch.setitem(parity.FAMILIES, "fake", _family({"episodes": [A]}))
    (tmp_path / "new.json").write_text(json.dumps({"episodes": [A]}))
    assert parity.main(["fake", "--new", str(tmp_path / "new.json")]) == 0
    assert sorted(path.name for path in tmp_path.iterdir()) == ["new.json"]


def test_record_sources_counts_source_source_key_and_closure_source_on_records_and_properties():
    document = {
        "features": [
            {"properties": {"source": "atc_shelters"}},
            {"properties": {"source": "oprhp_trails", "closure_source": "oprhp_trail_closures"}},
            {"source_key": "atc_trail_updates"},
            {"title": "no source named"},
        ]
    }
    assert parity.record_sources(document, "features") == (
        {"atc_shelters": 1, "atc_trail_updates": 1, "oprhp_trail_closures": 1, "oprhp_trails": 1},
        1,
    )


def test_changed_fields_tells_1_from_1_0_as_differences_does():
    assert parity.changed_fields("id x", '{"mile":1}', '{"mile":1.0}') == ["mile"]
    assert parity.changed_fields("field reviewed_at", '"2026-08-24"', '"2026-08-25"') == ["reviewed_at"]


# --- the answer per key --------------------------------------------------------


def _result(family: str, file_name: str, outcome: str = "no_differences", **fields) -> dict:
    return {
        "format": parity.RESULT_FORMAT,
        "family": family,
        "new_file": f"data/processed/dbt/{file_name}",
        "new_file_name": file_name,
        "records": "features",
        "key": "properties.id",
        "ordered": True,
        "compared_by_form_only": [],
        "outcome": outcome,
        "exit_code": 0 if outcome == "no_differences" else 1,
        "message": None,
        "old_records": 2,
        "new_records": 2,
        "explained": [],
        "differences": [],
        "old_sources": {},
        "old_records_naming_no_source": 0,
        "new_sources": {},
        "new_records_naming_no_source": 0,
        **fields,
    }


def _difference(field_path: str) -> dict:
    return {"what": "properties.id x", "old": "{}", "new": "{}", "fields": [field_path]}


TODAY = [
    TodayKey("poi_water.geojson", "artifact", "publish.collect_artifacts(), from poi/manifest.json"),
    TodayKey("poi_viewpoint.geojson", "artifact", "publish.collect_artifacts(), from poi/manifest.json"),
    TodayKey("poi_privy.geojson", "artifact", "publish.collect_artifacts(), from poi/manifest.json"),
    TodayKey("poi_shelter.geojson", "artifact", "publish.collect_artifacts(), from poi/manifest.json"),
    TodayKey("trails.fgb", "artifact", "publish.collect_artifacts(), from trails_manifest.json"),
]
DBT = [
    DbtKey(f"poi_{kind}.geojson", "poi_by_type_geojson", f"model.ourhike.pub_poi_{kind}", f"poi_{kind}.geojson")
    for kind in ("water", "viewpoint", "privy", "shelter")
]


def test_a_key_no_parity_result_covers_reads_not_ported_never_passing():
    results = {"poi_water": _result("poi_water", "poi_water.geojson")}
    rows, _, _ = key_rows(TODAY, DBT, results)
    verdicts = {row.key: row.verdict for row in rows}
    assert verdicts["poi_water.geojson"] == "equal"
    # No dbt exposure names it: today's exporter still writes it.
    assert verdicts["trails.fgb"] == "not_ported"
    # A dbt writer owns it, but no result compared its file.
    assert verdicts["poi_privy.geojson"] == "not_ported"
    assert "no parity result" in next(row.detail for row in rows if row.key == "poi_privy.geojson")


def test_a_safety_field_difference_ranks_first_in_the_rows_and_the_markdown():
    results = {
        "poi_viewpoint": _result(
            "poi_viewpoint", "poi_viewpoint.geojson", "differences", differences=[_difference("properties.name")]
        ),
        "poi_water": _result(
            "poi_water", "poi_water.geojson", "differences", differences=[_difference("properties.water_distance_ft")]
        ),
        "poi_shelter": _result("poi_shelter", "poi_shelter.geojson"),
    }
    rows, unmatched, new_keys = key_rows(TODAY, DBT, results)
    assert [row.key for row in rows[:2]] == ["poi_water.geojson", "poi_viewpoint.geojson"]
    assert rows[0].safety == ["water distance"]
    markdown = gate_report.render_markdown(rows, unmatched, new_keys, {"parity_dir": "d", "dbt_manifest": "m", "results": 3})
    assert markdown.index("`poi_water.geojson` — **safety: water distance**") < markdown.index("`poi_viewpoint.geojson`")
    assert "**1 key(s) differ on a safety field**" in markdown


def test_a_keys_only_result_says_its_records_were_withheld_and_which_side_lacks_one():
    lost = {"what": "properties.id x", "old": '{"name":"Lost Spring"}', "new": None, "fields": ["properties.name"]}
    result = parity.without_records(_result("poi_water", "poi_water.geojson", "differences", differences=[lost]))
    rows, unmatched, new_keys = key_rows(TODAY, DBT, {"poi_water": result})
    markdown = gate_report.render_markdown(rows, unmatched, new_keys, {"parity_dir": "d", "dbt_manifest": "m", "results": 1})

    assert "  - old: `(withheld: parity.py --keys-only)`\n  - new: `(absent)`" in markdown
    assert "Lost Spring" not in markdown


def test_an_explained_safety_difference_is_listed_for_approval_on_its_own_row():
    explained = {**_difference("properties.confidence"), "reason": "expected, an exact copy"}
    rows, _, _ = key_rows(TODAY, DBT, {"poi_water": _result("poi_water", "poi_water.geojson", explained=[explained])})
    water = next(row for row in rows if row.key == "poi_water.geojson")
    assert (water.verdict, water.safety) == ("equal_apart_from_listed", ["confidence"])
    assert water.listed[0].open_because == "it changes confidence, and its reason is not an exact copy's"


# --- the exact-copy standard: which listed differences come to the maintainer -----------------------------------------------

#: The changed fields of monthly run 31's two exact-copy groups and its seasonal taps, as its keys-only results list
#: them (field names only, read 2026-10-11 from the run's parity artifact): a restroom copy and a line copy today's
#: file alone holds, and a tap the dbt writer's alone holds.
RESTROOM_COPY_FIELDS = [
    *("geometry.coordinates", "geometry.type", "properties.confidence", "properties.id", "properties.lat"),
    *("properties.lon", "properties.name", "properties.poi_type", "properties.site_id", "properties.site_name"),
    *("properties.site_role", "properties.source", "properties.source_feature_id", "properties.trail_id", "type"),
]
LINE_COPY_FIELDS = [
    *("geometry.coordinates", "geometry.type", "properties.blaze_color", "properties.id", "properties.length_miles"),
    *("properties.name", "properties.source", "properties.trail_status", "type"),
]
SEASONAL_TAP_FIELDS = [
    *("geometry.coordinates", "geometry.type", "properties.confidence", "properties.description", "properties.id"),
    *("properties.lat", "properties.lon", "properties.poi_type", "properties.source", "properties.source_feature_id"),
    *("properties.trail_id", "properties.water_caution", "type"),
]
#: What a restroom copy and the copy staging kept differ on: their ids, and the site today's file folds them into.
RESTROOM_COPY_DIFFERS = [
    *("properties.id", "properties.site_id", "properties.site_name", "properties.site_role"),
    "properties.source_feature_id",
]
NEARBY = [
    TodayKey("nearby_poi.geojson", "artifact", "publish.collect_artifacts(), from nearby_manifest.json"),
    TodayKey("nearby_trails.geojson", "artifact", "publish.collect_artifacts(), from nearby_trails_manifest.json"),
]
NEARBY_DBT = [
    DbtKey("nearby_poi.geojson", "nearby_poi_geojson", "model.ourhike.pub_nearby_poi", "nearby_poi.geojson"),
    DbtKey("nearby_trails.geojson", "nearby_trails_geojson", "model.ourhike.pub_nearby_trails", "nearby_trails.geojson"),
]


def _explained(what: str, fields: list[str], reason: str, held_by: str = "old", **facts) -> dict:
    """One explained difference as a --keys-only result writes it: the key, the changed fields, the side holding it."""
    return {"what": what, "fields": fields, "reason": reason, "held_by": [held_by], **facts}


def _nearby(poi: list[dict], trails: list[dict]) -> dict:
    rows, _, _ = key_rows(
        NEARBY,
        NEARBY_DBT,
        {
            "nearby_poi": _result("nearby_poi", "nearby_poi.geojson", ordered=False, explained=poi),
            "nearby_trails": _result("nearby_trails", "nearby_trails.geojson", ordered=False, explained=trails),
        },
    )
    return {row.key: row for row in rows}


def test_an_explained_difference_on_no_safety_field_is_accepted_without_row_review():
    renamed = _explained("properties.id x", ["properties.name"], "expected, an exact copy", held_by="new")
    row = _nearby([renamed], [])["nearby_poi.geojson"]

    assert (row.verdict, row.safety, row.safety_accepted, row.listed[0].open_because) == (
        "equal_apart_from_listed",
        [],
        [],
        None,
    )


def test_an_exact_copy_carrying_its_originals_safety_values_is_accepted_without_row_review():
    """A restroom copy staging removed, whose kept copy the dbt writer publishes with the same confidence,
    differs from it in ids and site alone, so a hiker sees the same value and no row comes to the maintainer."""
    copy = _explained(
        "properties.id nyc_public_restrooms:row-b",
        RESTROOM_COPY_FIELDS,
        parity.POI_REASONS["exact_copy"],
        exact_copy_of="properties.id nyc_public_restrooms:row-a",
        differs_from_exact_copy=RESTROOM_COPY_DIFFERS,
    )
    rows = _nearby([copy], [])
    row = rows["nearby_poi.geojson"]

    assert (row.safety, row.safety_accepted, row.listed[0].open_because) == ([], ["confidence"], None)
    markdown = gate_report.render_markdown(list(rows.values()), [], [], {"parity_dir": "d", "dbt_manifest": "m", "results": 2})
    (line,) = [line for line in markdown.split("\n") if "row-b" in line]
    assert "accepted without row review by the exact-copy standard" in line
    assert "approve each row" not in line and "**safety" not in line
    assert "and 0 more carry an explained difference on one that stays open" in markdown
    assert "1 explained difference(s) on a safety field are accepted without row review by the exact-copy standard" in markdown


def test_an_exact_copy_whose_safety_value_differs_from_its_originals_stays_open_and_names_it():
    """The copy is an exact copy in today's file, and the record that still publishes now carries another confidence:
    a hiker would see a different value, so the row comes to the maintainer, naming the field and the record."""
    copy = _explained(
        "properties.id nyc_public_restrooms:row-b",
        RESTROOM_COPY_FIELDS,
        parity.POI_REASONS["exact_copy"],
        exact_copy_of="properties.id nyc_public_restrooms:row-a",
        differs_from_exact_copy=[*RESTROOM_COPY_DIFFERS, "properties.confidence"],
    )
    rows = _nearby([copy], [])
    row = rows["nearby_poi.geojson"]

    assert (row.safety, row.safety_accepted) == (["confidence"], [])
    assert row.listed[0].open_because == (
        "its confidence differs from that of properties.id nyc_public_restrooms:row-a, the record it is an exact copy of"
    )
    markdown = gate_report.render_markdown(list(rows.values()), [], [], {"parity_dir": "d", "dbt_manifest": "m", "results": 2})
    (line,) = [line for line in markdown.split("\n") if "row-b" in line]
    assert "(**safety: confidence**, open because its confidence differs" in line and "approve each row on its own" in line
    assert "and 1 more carry an explained difference on one that stays open" in markdown


def test_an_exact_copy_parity_names_no_original_for_stays_open():
    """A result written before the exact-copy standard, or a partner parity.py could not find once on its side, carries no partner: what a
    hiker sees is unread, so the row stays open rather than being accepted on the reason's word."""
    copy = _explained("properties.id nyc_public_restrooms:row-b", RESTROOM_COPY_FIELDS, parity.POI_REASONS["exact_copy"])
    row = _nearby([copy], [])["nearby_poi.geojson"]

    assert row.safety == ["confidence"]
    assert "names no record it copies" in row.listed[0].open_because


def test_a_copy_on_a_safety_field_another_reason_explains_stays_open_whatever_its_partner():
    """Only an exact-copy reason can accept a safety field: the seasonal taps carry a new confidence, which is a value
    a hiker sees change, so naming a partner does not accept them."""
    tap = _explained(
        "properties.id oprhp_facilities:13789",
        SEASONAL_TAP_FIELDS,
        parity.POI_REASONS["seasonal_tap"],
        held_by="new",
        exact_copy_of="properties.id oprhp_facilities:13790",
        differs_from_exact_copy=["properties.id"],
    )
    row = _nearby([tap], [])["nearby_poi.geojson"]

    assert row.safety == ["confidence"]
    assert row.listed[0].open_because == "it changes confidence, and its reason is not an exact copy's"


def test_monthly_run_31s_two_copy_groups_are_accepted_and_its_seasonal_taps_still_come_to_the_maintainer():
    """Run 31's safety-field groups as the exact-copy standard reads them once parity.py names each copy's partner: nearby_poi's 2 NYC
    restroom copies on confidence and nearby_trails' 57 copied lines on trail_status pass without row review (a line
    copy differs from the line the dbt writer keeps in its id alone); the 105 seasonal taps change a confidence a
    hiker sees and stay open, so nearby_poi.geojson still carries an open safety flag and nearby_trails.geojson none."""
    restrooms = [
        _explained(
            f"properties.id nyc_public_restrooms:row-copy-{n}",
            RESTROOM_COPY_FIELDS,
            parity.POI_REASONS["exact_copy"],
            exact_copy_of=f"properties.id nyc_public_restrooms:row-kept-{n}",
            differs_from_exact_copy=RESTROOM_COPY_DIFFERS,
        )
        for n in range(2)
    ]
    taps = [
        _explained(f"properties.id oprhp_facilities:{n}", SEASONAL_TAP_FIELDS, parity.POI_REASONS["seasonal_tap"], "new")
        for n in range(105)
    ]
    lines = [
        _explained(
            f"properties.id nyc_dot_greenways:row-copy-{n}",
            LINE_COPY_FIELDS,
            parity.NETWORK_COPY_REASON,
            exact_copy_of=f"properties.id nyc_dot_greenways:row-kept-{n}",
            differs_from_exact_copy=["properties.id"],
        )
        for n in range(57)
    ]
    rows = _nearby([*restrooms, *taps], lines)
    poi, trails = rows["nearby_poi.geojson"], rows["nearby_trails.geojson"]

    assert sum(bool(item.safety) and item.open_because is None for item in poi.listed) == 2
    assert {item.reason for item in poi.listed if item.open_because} == {parity.POI_REASONS["seasonal_tap"]}
    assert sum(bool(item.open_because) for item in poi.listed) == 105
    assert (poi.safety, poi.safety_accepted) == (["confidence"], ["confidence"])
    assert all(item.open_because is None for item in trails.listed)
    assert (trails.safety, trails.safety_accepted) == ([], ["trail_status"])
    markdown = gate_report.render_markdown(list(rows.values()), [], [], {"parity_dir": "d", "dbt_manifest": "m", "results": 2})
    assert "59 explained difference(s) on a safety field are accepted without row review by the exact-copy standard" in markdown
    assert "### `nearby_trails.geojson`\n" in markdown, (
        "no safety flag on a key whose only safety rows the exact-copy standard accepts"
    )


def test_the_exact_copy_reasons_are_the_two_staging_dedupe_reasons_and_each_family_giving_one_names_its_partner():
    assert {parity.NETWORK_COPY_REASON, parity.POI_REASONS["exact_copy"]} == parity.EXACT_COPY_REASONS
    assert {name for name, family in parity.FAMILIES.items() if family.copies} == {"nearby_poi", "nearby_trails"}


def test_status_is_a_safety_field_in_a_conditions_file_and_not_in_challenges_json():
    """A closure's `status` decides whether a hiker reads the trail as shut; a challenge's is draft or published."""
    today = [TodayKey("conditions/closures.json", "artifact", "x"), TodayKey("challenges.json", "artifact", "x")]
    dbt = [
        DbtKey("conditions/closures.json", "e", "model.ourhike.pub_conditions_closures", "conditions_closures.json"),
        DbtKey("challenges.json", "c", "model.ourhike.pub_challenges", "challenges.json"),
    ]
    results = {
        family: _result(family, file_name, "differences", differences=[_difference("status")])
        for family, file_name in (("closures", "conditions_closures.json"), ("challenges", "challenges.json"))
    }
    rows, _, _ = key_rows(today, dbt, results)
    assert {row.key: row.safety for row in rows} == {"conditions/closures.json": ["closure fields"], "challenges.json": []}
    assert rows[0].key == "conditions/closures.json"


def test_stamps_and_an_unordered_family_are_listed_never_called_equal():
    result = _result("poi_water", "poi_water.geojson", compared_by_form_only=["generated_at"], ordered=False)
    rows, _, _ = key_rows(TODAY, DBT, {"poi_water": result})
    water = next(row for row in rows if row.key == "poi_water.geojson")
    assert water.verdict == "equal_apart_from_listed"
    assert [item.what for item in water.listed] == ["field generated_at", "order"]


def test_two_absent_files_are_not_compared_rather_than_equal():
    rows, _, _ = key_rows(TODAY, DBT, {"poi_water": _result("poi_water", "poi_water.geojson", "neither_writes")})
    assert next(row.verdict for row in rows if row.key == "poi_water.geojson") == "not_compared"


def test_two_files_with_no_records_are_not_compared_unless_the_family_may_be_empty():
    """An empty file equal to an empty file says nothing about the writer's records, so 0/0 blocks go."""
    today = [TodayKey("conditions/work_projects.json", "artifact", "x"), TodayKey("poi_trailhead.geojson", "artifact", "x")]
    dbt = [
        DbtKey("conditions/work_projects.json", "e", "model.ourhike.pub_conditions_work_projects", "work_projects.json"),
        DbtKey("poi_trailhead.geojson", "e", "model.ourhike.pub_poi_trailhead", "poi_trailhead.geojson"),
    ]
    results = {
        family: _result(family, file_name, old_records=0, new_records=0)
        for family, file_name in (("work_projects", "work_projects.json"), ("poi_trailhead", "poi_trailhead.geojson"))
    }
    rows = {row.key: row for row in key_rows(today, dbt, results)[0]}

    # Work projects' reviewed file is empty on purpose, so it may compare empty too.
    work = rows["conditions/work_projects.json"]
    assert (work.verdict, work.blocks_go) == ("equal_apart_from_listed", False)
    assert "#760" in next(item.reason for item in work.listed if item.what == "records")
    trailhead = rows["poi_trailhead.geojson"]
    assert (trailhead.verdict, trailhead.blocks_go) == ("equal_apart_from_listed", False)
    assert "ALLOWED_EMPTY_POI_TYPES" in next(item.reason for item in trailhead.listed if item.what == "records")


def test_only_the_poi_types_export_poi_may_publish_empty_and_three_conditions_families_may_compare_no_records():
    """One home for the POI types: lib/poi_schema.ALLOWED_EMPTY_POI_TYPES. Work projects is the maintainer's own
    choice, and so are closures and reports; highlights is not on it."""
    from lib.poi_schema import ALLOWED_EMPTY_POI_TYPES

    expected = {f"poi_{kind}{version}" for kind in ALLOWED_EMPTY_POI_TYPES for version in ("", "_v2")}
    assert expected == {"poi_trailhead", "poi_trailhead_v2"}
    assert set(gate_report.MAY_COMPARE_NO_RECORDS) == expected | {"work_projects", "closures", "reports"}
    assert set(gate_report.MAY_COMPARE_NO_RECORDS) <= set(parity.FAMILIES)
    assert all(reason.strip() for reason in gate_report.MAY_COMPARE_NO_RECORDS.values())


def test_an_empty_conditions_family_counts_only_while_ci_compares_its_writer_on_rows(tmp_path, monkeypatch):
    """An hour of the soak that compared two empty conditions/closures.json,
    conditions/reports.json or conditions/work_projects.json files counts, because CI's fixture families compare each
    writer on rows each time pipeline-tests.yml's dbt job runs. So the fixtures keep a row each family publishes, and
    the parity step keeps all three lines: without either, nothing would compare that writer on a row while the empty
    soak still counted. work_projects compared none until 2026-10-15 ('no differences across 0 work_projects' in run
    38610267739, beside 3 closures and 3 reports), because both sides read reference/work_projects.json, empty by the
    maintainer's decision of 2026-08-20 on #760; both now read make_dbt_fixtures.py's stand-in
    (lib/work_projects.FIXTURE_STAND_IN), and tests/test_extract_fixtures.py holds fixture mode's half of that."""
    import yaml

    import make_dbt_fixtures
    from lib.work_projects import FIXTURE_STAND_IN, file_problems, is_reviewed, published_rows

    answers = make_dbt_fixtures._ourhike_postgres()
    verified = [row for row in answers["closures"]["rows"] if row["moderation_status"] == "verified"]
    public = [
        row for row in answers["reports"]["rows"] if row["status"] in ("verified", "resolved") and row["visibility"] == "public"
    ]
    stand_in = json.loads(make_dbt_fixtures.closures_and_warnings_fixtures()[FIXTURE_STAND_IN])
    assert is_reviewed(stand_in) and file_problems(stand_in) == []
    workdays = published_rows(stand_in)
    assert verified and public and workdays, "with no row in a fixture, CI compares that writer on none again"
    # Each reason gives the count CI compares on, so a fixture that grows or shrinks takes its reason with it.
    reasons = gate_report.MAY_COMPARE_NO_RECORDS
    assert f"{len(verified)} verified closures" in reasons["closures"]
    assert f"{len(public)} public reports" in reasons["reports"]
    assert f"{len(workdays)} invented workdays" in reasons["work_projects"]
    (tmp_path / FIXTURE_STAND_IN).parent.mkdir(parents=True)
    (tmp_path / FIXTURE_STAND_IN).write_text(json.dumps(stand_in), encoding="utf-8")
    monkeypatch.setattr(parity, "RAW_DIR", tmp_path)
    assert len(parity._work_projects_old()["work_projects"]) == len(workdays), "the old side reads the stand-in"
    workflow = Path(__file__).resolve().parents[2] / ".github" / "workflows" / "pipeline-tests.yml"
    (step,) = [
        step
        for job in yaml.safe_load(workflow.read_text(encoding="utf-8"))["jobs"].values()
        for step in job.get("steps") or []
        if step.get("name") == "Parity with today's exporters"
    ]
    for family in ("closures", "reports", "work_projects"):
        line = f"parity.py --json-dir data/processed/parity {family} --new data/processed/dbt/conditions_{family}.json"
        assert line in step["run"], family


def test_a_key_pattern_matches_whichever_placeholder_each_side_writes():
    today = [TodayKey("suggested_hikes_detail_{id}.json", "artifact", "x")]
    dbt = [DbtKey("suggested_hikes_detail_{number}.json", "e", "model.ourhike.w", "suggested_hikes_detail.json")]
    rows, _, new_keys = key_rows(today, dbt, {"d": _result("d", "suggested_hikes_detail.json")})
    assert (rows[0].verdict, new_keys) == ("equal_apart_from_listed", [])
    assert "the cut into one object each is not" in rows[0].listed[-1].reason


# --- every key today's pipeline publishes ---------------------------------------


@pytest.fixture(scope="module")
def today():
    return gate_report.today_keys()


def test_today_keys_holds_every_family_kind_of_key(today):
    keys = {entry.key for entry in today}
    for expected in (
        "trails.geojson",
        "trails.fgb",
        "trail_miles.json",
        "poi_water.geojson",
        "conditions/closures.json",
        "conditions/weather/{cell}.json",
        "conditions/weather_index.json",
        "suggested_hikes_detail_{id}.json",
        "trail_graph_profile_cell_{cell}.json",
        "nearby_trails_cell_{cell}.pmtiles",
        "background_z11.pmtiles",
        "podcasts/episodes.json",
        "osm_water.geojson",
        "latest.json",
    ):
        assert expected in keys, expected
    assert len(keys) == len(today), "a key is listed twice"


def test_today_keys_refuses_a_manifest_publish_reads_and_it_has_no_stub_for(monkeypatch):
    real = gate_report.manifests_publish_reads
    monkeypatch.setattr(gate_report, "manifests_publish_reads", lambda module: real(module) | {"brand_new_manifest.json"})
    with pytest.raises(RuntimeError, match="brand_new_manifest.json"):
        gate_report.today_keys()


def test_cut_cells_spells_its_index_context_and_cell_names_as_the_stubs_do():
    source = (Path(gate_report.__file__).parent / "cut_cells.py").read_text()
    for spelling in ('f"{family}_cells.json"', 'f"{family}_context.pmtiles"', 'f"{family}_cell_{cell_name(c[0], c[1])}.pmtiles"'):
        assert spelling in source, spelling


def test_every_key_the_app_fetches_is_one_today_keys_lists(today):
    """The app's own census (tests/test_published_key_contract.py reads it out of client/src) is inside this one.

    A key a phone asks for that today_keys() left out would be a key the gate
    report never answers for, which is the one way this report could pass a
    key by not looking at it. Apart from the keys only a dbt writer publishes
    (test_published_key_contract.DBT_ONLY_CLIENT_KEYS, the one list of them):
    today's pipeline has no file of theirs to compare, so they are not gate
    items, and the report lists them under the keys a dbt exposure names that
    today's pipeline does not publish."""
    import re

    from test_published_key_contract import DBT_ONLY_CLIENT_KEYS, client_keys

    patterns = [re.compile(re.escape(gate_report.key_pattern(entry.key)).replace(r"\{\}", "[^/]+")) for entry in today]
    missing = {
        key: asked_by
        for key, asked_by in client_keys().items()
        if key not in DBT_ONLY_CLIENT_KEYS and not any(p.fullmatch(key) for p in patterns)
    }
    assert not missing


# --- the command line ------------------------------------------------------------


def test_main_writes_both_files_and_exits_2_without_results(tmp_path, capsys):
    manifest = {
        "nodes": {"model.ourhike.pub_spurs": {"config": {"materialized": "phone_file", "location": "spurs.json"}}},
        "exposures": {
            "exposure.ourhike.spurs_json": {
                "name": "spurs_json",
                "config": {"meta": {"r2_keys": ["spurs.json"]}},
                "depends_on": {"nodes": ["model.ourhike.pub_spurs"]},
            }
        },
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    (tmp_path / "parity").mkdir()
    arguments = [
        "--parity-dir",
        str(tmp_path / "parity"),
        "--out",
        str(tmp_path / "out"),
        "--dbt-manifest",
        str(tmp_path / "manifest.json"),
    ]
    assert gate_report.main(arguments) == 2
    (tmp_path / "parity" / "spurs.json").write_text(json.dumps(_result("spurs", "spurs.json")))
    assert gate_report.main(arguments) == 0
    report = json.loads((tmp_path / "out" / "gate_report.json").read_text())
    spurs = next(row for row in report["keys"] if row["key"] == "spurs.json")
    assert spurs["verdict"] == "equal"
    assert report["counts"]["not_ported"] == len(report["keys"]) - 1
    assert "## Not yet ported" in (tmp_path / "out" / "gate_report.md").read_text()
    # Nothing blocks: every other key is one the dbt path does not write.
    assert (report["blocking"], gate_report.main([*arguments, "--strict"])) == ([], 0)
    (tmp_path / "parity" / "spurs.json").write_text(
        json.dumps(_result("spurs", "spurs.json", "differences", differences=[_difference("junction_mile")]))
    )
    assert gate_report.main([*arguments, "--strict"]) == 1
    assert gate_report.main(arguments) == 0, "without --strict a written report exits 0 whatever it says"

    summary = tmp_path / "step_summary.md"
    summary.write_text("| family | status |\n")  # parity_lane.py --join writes its table to the same page first
    assert gate_report.main([*arguments, "--summary", str(summary)]) == 0
    report = json.loads((tmp_path / "out" / "gate_report.json").read_text())
    page = summary.read_text()
    assert page.startswith("| family | status |\n### The gate's per-key report\n")
    assert f"- {len(report['keys'])} keys today's pipeline publishes: 1 differs, 0 not_compared, " in page
    assert "- **1 block go** on this report's own reading of the gate, for the maintainer to confirm." in page


def test_a_record_from_a_source_todays_exporters_never_read_is_listed_once_as_new_data():
    """New data: parity explains it, and the report lists it by reason, with no field called changed and
    no safety flag, because there is no old record to approve it against; new_data_report.py reviews it."""
    new_data = [
        {
            "what": f"properties.id ncta_points:{{NC-{index}}}",
            "old": None,
            "new": "{}",
            "fields": ["properties.poi_type", "properties.confidence", "geometry.coordinates[]"],
            "reason": parity.POI_REASONS["new_source"],
        }
        for index in range(3)
    ]
    results = {"poi_water": _result("poi_water", "poi_water.geojson", explained=new_data)}
    rows, unmatched, new_keys = key_rows(TODAY, DBT, results)
    water = next(row for row in rows if row.key == "poi_water.geojson")
    assert (water.verdict, water.safety) == ("equal_apart_from_listed", [])
    markdown = gate_report.render_markdown(rows, unmatched, new_keys, {"parity_dir": "d", "dbt_manifest": "m", "results": 1})
    lines = [line for line in markdown.split("\n") if parity.NEW_DATA_REASON in line]
    assert len(lines) == 1
    assert lines[0].startswith("- listed, 3:")
    assert "Changed:" not in lines[0]
    assert "**0 key(s) differ on a safety field**, and 0 more" in markdown
