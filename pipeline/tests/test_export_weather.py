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
from lib import hrrr_grid, nbm_grid
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
    "zones": {
        "county/NHC007": [[562, 2074], [563, 2076]],
        "fire/NHZ021": [[562, 2074]],
        "fire/NHZ022": [[563, 2076]],
        "forecast/NHZ002": [[562, 2074], [563, 2076]],
    },
    "known_zones": {"forecast": ["NHZ002"], "fire": ["NHZ021", "NHZ022"], "county": ["NHC007"]},
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


def test_each_square_carries_the_nws_zones_a_phone_would_ask_about(tmp_path, cycle):
    _, documents = bake(tmp_path, cycle)

    whites = documents["n44w072"]
    zones = dict(zip(map(tuple, whites["squares"]), whites["zones"], strict=True))
    assert zones[(562, 2074)] == ["county/NHC007", "fire/NHZ021", "forecast/NHZ002"]
    assert zones[(563, 2076)] == ["county/NHC007", "fire/NHZ022", "forecast/NHZ002"]
    # No zone outline reaches this square: an empty list, so the phone knows
    # it has nothing to ask NWS about rather than guessing a neighbour's.
    assert documents["n41w074"]["zones"] == [[]]


def test_a_squares_file_from_before_zones_is_refused(tmp_path, cycle):
    old = {k: v for k, v in SQUARES.items() if k not in ("zones", "known_zones")}

    with pytest.raises(RuntimeError, match="zones"):
        bake(tmp_path, cycle, squares=old)


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
    monkeypatch.setattr(export_weather, "HRRR_CYCLE_PATH", raw / "hrrr_cycle.json")  # absent: NBM alone
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


# --------------------------------------------------------------------------
# HRRR (the HRRR slice). Synthetic full-size rasters on HRRR's pinned grid,
# each cell's value encoding its own row and column in tenths of a degree,
# written as GeoTIFFs carrying the unit tag GDAL puts on a GRIB message.

HRRR_GRID = Affine(hrrr_grid.CELL_M, 0, hrrr_grid.ORIGIN_X, 0, -hrrr_grid.CELL_M, hrrr_grid.ORIGIN_Y)


def hrrr_encoded(offset: float = 0.0) -> np.ndarray:
    rows, cols = np.mgrid[0 : hrrr_grid.HEIGHT, 0 : hrrr_grid.WIDTH]
    return (((rows * 7 + cols * 3) % 400) / 10.0 - 10.0 + offset).astype(np.float64)


def hrrr_expected(row: int, col: int, offset: float = 0.0) -> float:
    return round(((row * 7 + col * 3) % 400) / 10.0 - 10.0 + offset, 1)


def write_hrrr(path, array, unit="[C]", transform=HRRR_GRID):
    path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        width=array.shape[1],
        height=array.shape[0],
        count=1,
        dtype="float64",
        crs=hrrr_grid.PROJ4,
        transform=transform,
    ) as ds:
        ds.write(array, 1)
        ds.update_tags(1, GRIB_UNIT=unit)


# The summit's HRRR cell and Lakes of the Clouds', and a lake cell in the
# Hudson cell that borrows its land neighbour.
SQUARES_HRRR = {
    **SQUARES,
    "hrrr_grid": {"proj4": hrrr_grid.PROJ4, "origin": [hrrr_grid.ORIGIN_X, hrrr_grid.ORIGIN_Y], "cell_m": hrrr_grid.CELL_M},
    "hrrr_cells": {"n44w072": [[216, 1588], [216, 1589]], "n41w074": [[341, 1547]]},
    "hrrr_reads": [[216, 1588, 216, 1588, 1419], [216, 1589, 216, 1589, 1306], [341, 1547, 340, 1547, 212]],
    "hrrr_water_kept": [],
}


@pytest.fixture
def hrrr(tmp_path):
    write_hrrr(tmp_path / "hrrr/r/t2m_f01.grb2", hrrr_encoded(0.0))
    write_hrrr(tmp_path / "hrrr/r/t2m_f02.grb2", hrrr_encoded(0.5))
    return {
        "model": "hrrr",
        "cycle": "2026-09-25T06:00Z",
        "fields": {"temp2m": [["2026-09-25T07:00Z", "hrrr/r/t2m_f01.grb2"], ["2026-09-25T08:00Z", "hrrr/r/t2m_f02.grb2"]]},
    }


def bake_with_hrrr(tmp_path, cycle_doc, hrrr_doc, squares=SQUARES_HRRR):
    from datetime import UTC, datetime

    return export_weather.bake(squares, cycle_doc, tmp_path, datetime(2026, 9, 25, 12, 30, tzinfo=UTC), hrrr_doc)


def test_each_hrrr_cell_reads_its_own_temperature_and_carries_its_height(tmp_path, cycle, hrrr):
    index, documents = bake_with_hrrr(tmp_path, cycle, hrrr)

    block = documents["n44w072"]["hrrr"]
    assert block["cells"] == [[216, 1588], [216, 1589]]
    assert block["height"] == [1419, 1306]
    assert block["temp"] == [
        [hrrr_expected(216, 1588), hrrr_expected(216, 1588, 0.5)],
        [hrrr_expected(216, 1589), hrrr_expected(216, 1589, 0.5)],
    ]
    assert block["times"] == ["2026-09-25T07:00Z", "2026-09-25T08:00Z"]
    assert block["units"] == {"temp": "C", "height": "m"} and block["borrowed"] == []
    # A mirrored read would have returned another cell's number.
    assert hrrr_expected(hrrr_grid.HEIGHT - 1 - 216, 1589) != hrrr_expected(216, 1589)
    assert index["hrrr_cycle"] == "2026-09-25T06:00Z" and index["hrrr_grid"]["cell_m"] == 3000.0


def test_a_water_hrrr_cell_reads_its_land_neighbour_and_says_so(tmp_path, cycle, hrrr):
    _, documents = bake_with_hrrr(tmp_path, cycle, hrrr)

    block = documents["n41w074"]["hrrr"]
    assert block["temp"][0][0] == hrrr_expected(340, 1547)
    assert block["height"] == [212] and block["borrowed"] == [[0, 340, 1547]]


def test_without_an_hrrr_run_every_cell_says_null_and_nbm_still_publishes(tmp_path, cycle):
    index, documents = bake_with_hrrr(tmp_path, cycle, None)

    assert all(document["hrrr"] is None for document in documents.values())
    assert index["hrrr_cycle"] is None
    assert documents["n44w072"]["fields"]["temp"]["values"]  # the forecast itself is intact


def test_an_hrrr_file_not_in_celsius_is_refused(tmp_path, cycle, hrrr):
    write_hrrr(tmp_path / "hrrr/r/t2m_f01.grb2", hrrr_encoded(0.0) + 273.15, unit="[K]")

    with pytest.raises(RuntimeError, match="Celsius"):
        bake_with_hrrr(tmp_path, cycle, hrrr)


def test_an_hrrr_temperature_outside_any_real_one_stops_the_bake(tmp_path, cycle, hrrr):
    hot = hrrr_encoded(0.0)
    hot[216, 1589] = 95.0

    write_hrrr(tmp_path / "hrrr/r/t2m_f02.grb2", hot)

    with pytest.raises(RuntimeError, match="outside"):
        bake_with_hrrr(tmp_path, cycle, hrrr)


def test_an_hrrr_file_on_a_moved_grid_is_refused(tmp_path, cycle, hrrr):
    moved = Affine(hrrr_grid.CELL_M, 0, hrrr_grid.ORIGIN_X + hrrr_grid.CELL_M, 0, -hrrr_grid.CELL_M, hrrr_grid.ORIGIN_Y)
    write_hrrr(tmp_path / "hrrr/r/t2m_f01.grb2", hrrr_encoded(0.0), transform=moved)

    with pytest.raises(RuntimeError, match="not on HRRR"):
        bake_with_hrrr(tmp_path, cycle, hrrr)


def test_a_squares_file_from_before_hrrr_is_refused_when_hrrr_was_fetched(tmp_path, cycle, hrrr):
    with pytest.raises(RuntimeError, match="HRRR"):
        bake_with_hrrr(tmp_path, cycle, hrrr, squares=SQUARES)
