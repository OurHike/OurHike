"""gate_report.py and parity.py --json-dir: decision 30's one answer per R2 key, from the shadow run's results."""

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
        "dropped_before_comparing": [],
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


def test_an_explained_safety_difference_is_listed_for_approval_on_its_own_row():
    explained = {**_difference("properties.confidence"), "reason": "expected by decision 40"}
    rows, _, _ = key_rows(TODAY, DBT, {"poi_water": _result("poi_water", "poi_water.geojson", explained=[explained])})
    water = next(row for row in rows if row.key == "poi_water.geojson")
    assert (water.verdict, water.safety) == ("equal_apart_from_listed", ["confidence"])


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


def test_stamps_volatile_and_an_unordered_family_are_listed_never_called_equal():
    result = _result("poi_water", "poi_water.geojson", compared_by_form_only=["generated_at"], ordered=False)
    rows, _, _ = key_rows(TODAY, DBT, {"poi_water": result})
    water = next(row for row in rows if row.key == "poi_water.geojson")
    assert water.verdict == "equal_apart_from_listed"
    assert [item.what for item in water.listed] == ["field generated_at", "order"]


def test_two_absent_files_are_not_compared_rather_than_equal():
    rows, _, _ = key_rows(TODAY, DBT, {"poi_water": _result("poi_water", "poi_water.geojson", "neither_writes")})
    assert next(row.verdict for row in rows if row.key == "poi_water.geojson") == "not_compared"


def test_a_key_pattern_matches_whichever_placeholder_each_side_writes():
    today = [TodayKey("suggested_hikes_detail_{id}.json", "artifact", "x")]
    dbt = [DbtKey("suggested_hikes_detail_{number}.json", "e", "model.ourhike.w", "suggested_hikes_detail.json")]
    rows, _, new_keys = key_rows(today, dbt, {"d": _result("d", "suggested_hikes_detail.json")})
    assert (rows[0].verdict, new_keys) == ("equal_apart_from_listed", [])
    assert "the cut into one object each is not" in rows[0].listed[-1].reason


def test_the_two_reports_and_parity_agree_on_the_result_format():
    import new_data_report

    assert gate_report.PARITY_RESULT_FORMAT == parity.RESULT_FORMAT == new_data_report.PARITY_RESULT_FORMAT


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
    key by not looking at it."""
    import re

    from test_published_key_contract import client_keys

    patterns = [re.compile(re.escape(gate_report.key_pattern(entry.key)).replace(r"\{\}", "[^/]+")) for entry in today]
    missing = {key: asked_by for key, asked_by in client_keys().items() if not any(p.fullmatch(key) for p in patterns)}
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
