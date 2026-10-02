"""step_weather_squares.py lands squares.json whole, and refuses the files export_weather_alerts.py refuses (WN03)."""

import json

import duckdb
import pytest

import step_weather_squares

DOCUMENT = {
    "schema": 4,
    "release": "2026-09-25",
    "cells": {"n44w072": [[562, 2074], [563, 2076]], "n44w071": [[563, 2076]]},
    "zones": {"forecast/NHZ002": [[562, 2074]]},
    "known_zones": {"forecast": ["NHZ002"]},
    "zone_files": {"forecast": "z_16ap26.zip"},
}


def test_the_document_lands_whole_as_one_row_under_its_release(tmp_path):
    squares = tmp_path / "squares.json"
    squares.write_text(json.dumps(DOCUMENT))
    warehouse = tmp_path / "warehouse.duckdb"

    assert step_weather_squares.main(["--warehouse", str(warehouse), "--squares", str(squares)]) == 0

    with duckdb.connect(str(warehouse)) as con:
        rows = con.execute("select release, document_json, _loaded_at from derived.weather_squares").fetchall()
    assert len(rows) == 1
    release, document_json, loaded_at = rows[0]
    assert (release, json.loads(document_json)) == ("2026-09-25", DOCUMENT)
    assert loaded_at is not None


def test_a_second_run_replaces_the_row_rather_than_adding_one(tmp_path):
    squares = tmp_path / "squares.json"
    warehouse = tmp_path / "warehouse.duckdb"
    for release in ("2026-09-25", "2026-10-02"):
        squares.write_text(json.dumps({**DOCUMENT, "release": release}))
        step_weather_squares.main(["--warehouse", str(warehouse), "--squares", str(squares)])

    with duckdb.connect(str(warehouse)) as con:
        assert con.execute("select release from derived.weather_squares").fetchall() == [("2026-10-02",)]


def test_a_squares_file_from_before_zones_is_refused_as_export_weather_alerts_refuses_it(tmp_path):
    squares = tmp_path / "squares.json"
    squares.write_text(json.dumps({key: value for key, value in DOCUMENT.items() if key != "zones"}))

    with pytest.raises(SystemExit, match="predates each square's zones; run build_weather_squares.py first"):
        step_weather_squares.main(["--warehouse", str(tmp_path / "warehouse.duckdb"), "--squares", str(squares)])
    assert not (tmp_path / "warehouse.duckdb").exists()


def test_a_missing_squares_file_stops_the_build_and_says_who_writes_it(tmp_path):
    with pytest.raises(SystemExit, match="build_weather_squares.py writes it"):
        step_weather_squares.main(["--warehouse", str(tmp_path / "warehouse.duckdb"), "--squares", str(tmp_path / "none.json")])
