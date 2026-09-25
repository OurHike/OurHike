"""Tests for export_weather.py (#1056).

The rasters here are synthetic and full-size, on NBM's pinned grid, and each
square's value encodes its own row and column - so a read that mirrored,
transposed or shifted the grid (WEATHER.md §6's first trap) returns another
square's number and fails, rather than returning a plausible one."""

import json

import numpy as np
import pytest
import rasterio
from rasterio.transform import Affine

import export_weather
import publish
from lib import nbm_grid
from lib.r2_keys import validate_key

NODATA = -9999
GRID = Affine(nbm_grid.SQUARE_M, 0, nbm_grid.ORIGIN_X, 0, -nbm_grid.SQUARE_M, nbm_grid.ORIGIN_Y)


def encoded(offset: int = 0) -> np.ndarray:
    rows, cols = np.mgrid[0 : nbm_grid.HEIGHT, 0 : nbm_grid.WIDTH]
    return ((rows * 7 + cols * 3 + offset) % 90).astype(np.int16)


def expected(row: int, col: int, offset: int = 0) -> int:
    return (row * 7 + col * 3 + offset) % 90


def write_tif(path, array, transform=GRID):
    path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        width=array.shape[1],
        height=array.shape[0],
        count=1,
        dtype="int16",
        crs=nbm_grid.PROJ4,
        transform=transform,
        nodata=NODATA,
        compress="lzw",
    ) as ds:
        ds.write(array, 1)


SQUARES = {
    "schema": 1,
    "release": "2026-09-24-4",
    "grid": {"proj4": nbm_grid.PROJ4, "origin": [nbm_grid.ORIGIN_X, nbm_grid.ORIGIN_Y], "square_m": nbm_grid.SQUARE_M},
    "cells": {"n44w072": [[562, 2074], [563, 2076]], "n41w074": [[712, 2007]]},
    "borrowed": [[[712, 2007], [711, 2007]]],
    "water_kept": [],
    "outside_grid": ["n61w150"],
}


@pytest.fixture
def cycle(tmp_path):
    write_tif(tmp_path / "nbm/c/temp/h1.tif", encoded(0))
    write_tif(tmp_path / "nbm/c/temp/h2.tif", encoded(1))
    tstm = encoded(0)
    tstm[563, 2076] = NODATA
    write_tif(tmp_path / "nbm/c/tstm01/h1.tif", tstm)
    return {
        "version": "blendv5.0",
        "cycle": "2026-09-25T11:00Z",
        "fields": {
            "temp": [["2026-09-25T12:00Z", "nbm/c/temp/h1.tif"], ["2026-09-25T13:00Z", "nbm/c/temp/h2.tif"]],
            "tstm01": [["2026-09-25T12:00Z", "nbm/c/tstm01/h1.tif"]],
        },
    }


def bake(tmp_path, cycle_doc, squares=SQUARES):
    from datetime import UTC, datetime

    return export_weather.bake(squares, cycle_doc, tmp_path, datetime(2026, 9, 25, 12, 30, tzinfo=UTC))


def test_each_square_reads_its_own_value_not_a_mirrored_one(tmp_path, cycle):
    _, documents = bake(tmp_path, cycle)

    whites = documents["n44w072"]
    for i, (row, col) in enumerate(whites["squares"]):
        assert whites["fields"]["temp"]["values"][i] == [expected(row, col, 0), expected(row, col, 1)]
        # And the mirrored square really would have read differently, so the
        # assertion above is not passing by coincidence.
        assert expected(nbm_grid.HEIGHT - 1 - row, col) != expected(row, col)


def test_a_water_square_reads_its_land_neighbour_and_says_so(tmp_path, cycle):
    # WEATHER.md §6's second trap: Bear Mountain's square is the Hudson.
    _, documents = bake(tmp_path, cycle)

    hudson = documents["n41w074"]
    assert hudson["squares"] == [[712, 2007]]
    assert hudson["fields"]["temp"]["values"][0][0] == expected(711, 2007)
    assert hudson["borrowed"] == [[0, 711, 2007]]


def test_a_value_nbm_left_empty_is_null_never_zero(tmp_path, cycle):
    _, documents = bake(tmp_path, cycle)

    whites = documents["n44w072"]
    i = whites["squares"].index([563, 2076])
    assert whites["fields"]["tstm01"]["values"][i] == [None]


def test_fields_keep_their_own_lengths_rather_than_being_padded(tmp_path, cycle):
    _, documents = bake(tmp_path, cycle)

    fields = documents["n44w072"]["fields"]
    assert len(fields["temp"]["times"]) == 2 and len(fields["tstm01"]["times"]) == 1
    assert all(len(v) == 1 for v in fields["tstm01"]["values"])


def test_a_value_outside_the_fields_physical_range_stops_the_bake(tmp_path, cycle):
    hot = encoded(0)
    hot[562, 2074] = 400  # 400 F: a decode error, not weather
    write_tif(tmp_path / "nbm/c/temp/h1.tif", hot)

    with pytest.raises(RuntimeError, match="outside"):
        bake(tmp_path, cycle)


def test_a_file_on_a_moved_grid_is_refused(tmp_path, cycle):
    moved = Affine(nbm_grid.SQUARE_M, 0, nbm_grid.ORIGIN_X + nbm_grid.SQUARE_M, 0, -nbm_grid.SQUARE_M, nbm_grid.ORIGIN_Y)
    write_tif(tmp_path / "nbm/c/temp/h1.tif", encoded(0), transform=moved)

    with pytest.raises(RuntimeError, match="not on NBM"):
        bake(tmp_path, cycle)


def test_the_index_names_every_cell_and_the_ones_nothing_forecasts(tmp_path, cycle):
    index, documents = bake(tmp_path, cycle)

    assert index["cells"] == {"n41w074": {"squares": 1}, "n44w072": {"squares": 2}}
    assert index["outside_grid"] == ["n61w150"]
    assert index["cycle"] == "2026-09-25T11:00Z"
    assert index["source"] == "NOAA National Blend of Models (NBM) v5.0"
    assert documents["n44w072"]["units"] == {"temp": "F", "tstm01": "%"}


def test_a_field_the_export_has_no_range_for_is_refused(tmp_path, cycle):
    cycle["fields"]["mystery"] = cycle["fields"]["temp"]

    with pytest.raises(RuntimeError, match="mystery"):
        bake(tmp_path, cycle)


def test_publish_collects_every_cell_under_a_legal_conditions_key(tmp_path, monkeypatch, cycle):
    raw = tmp_path / "raw"
    processed = tmp_path / "processed"
    (raw / "nbm").mkdir(parents=True)
    (tmp_path / "nbm").rename(raw / "nbm")
    (raw / "squares.json").write_text(json.dumps(SQUARES))
    (raw / "cycle.json").write_text(json.dumps(cycle))
    monkeypatch.setattr(export_weather, "WEATHER_RAW", raw)
    monkeypatch.setattr(export_weather, "SQUARES_PATH", raw / "squares.json")
    monkeypatch.setattr(export_weather, "CYCLE_PATH", raw / "cycle.json")
    monkeypatch.setattr(export_weather, "CONDITIONS_DIR", processed / "conditions")
    monkeypatch.setattr(export_weather, "CELL_DIR", processed / "conditions" / "weather")
    monkeypatch.setattr(export_weather, "INDEX_PATH", processed / "conditions" / "weather_index.json")
    monkeypatch.setattr(export_weather, "MANIFEST_PATH", processed / "weather_manifest.json")
    monkeypatch.setattr(export_weather, "to_manifest_path", str)
    monkeypatch.setattr(publish, "PROCESSED_DIR", processed)
    monkeypatch.setattr(publish, "from_manifest_path", lambda p: __import__("pathlib").Path(p))

    export_weather.main()
    artifacts = publish.collect_artifacts()

    weather = sorted(k for k in artifacts if k.startswith("conditions/weather"))
    assert weather == [
        "conditions/weather/n41w074.json",
        "conditions/weather/n44w072.json",
        "conditions/weather_index.json",
    ]
    assert all(validate_key(k) is None for k in weather)
