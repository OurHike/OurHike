"""Tests for check_dem_archive.py - the DEM publish gate (#186).

The gate's whole job is refusing to ship an archive with a hole, a bad tile
or a lying header, so each test builds a real (tiny) archive and breaks it
in exactly one way. Good archives come from export_dem.main itself - the
gate must pass what the exporter builds, or it gates nothing."""

import argparse
import io
import json

import numpy as np
import pytest
from PIL import Image
from pmtiles.tile import Compression, TileType, zxy_to_tileid
from pmtiles.writer import write
from requests_mock import ANY as ANY_URL
from shapely.geometry import box, mapping, shape

import check_dem_archive
import export_dem
from export_dem import build_header, quantize_unit
from tests.test_export_dem import terrarium_png

NE_QUADRANT_BOX = box(30.0, 30.0, 80.0, 70.0)


def region_file(tmp_path):
    path = tmp_path / "region.geojson"
    path.write_text(json.dumps(mapping(NE_QUADRANT_BOX)))
    return path


def build_archive(tmp_path, requests_mock, monkeypatch, **overrides):
    monkeypatch.setattr(export_dem, "DEM_TILE_URL", "https://dem.test/{z}/{x}/{y}.png")
    requests_mock.get(ANY_URL, content=terrarium_png(np.full((256, 256), 250.5)))
    args = argparse.Namespace(
        region=region_file(tmp_path),
        out=tmp_path / "dem.pmtiles",
        min_zoom=0,
        max_zoom=2,
        quantize_step=0.5,
        workers=1,
        limit=0,
        name="test DEM",
    )
    for key, value in overrides.items():
        setattr(args, key, value)
    export_dem.main(args)
    return args.out


def check(archive, tmp_path, min_zoom=0, max_zoom=2):
    region = shape(json.loads(region_file(tmp_path).read_text()))
    return check_dem_archive.check_archive(archive, region, min_zoom, max_zoom)


def test_passes_the_archive_the_exporter_builds(tmp_path, requests_mock, monkeypatch):
    archive = build_archive(tmp_path, requests_mock, monkeypatch)

    assert check(archive, tmp_path) == []


def test_main_exits_zero_on_a_good_archive(tmp_path, requests_mock, monkeypatch, capsys):
    archive = build_archive(tmp_path, requests_mock, monkeypatch)

    check_dem_archive.main(argparse.Namespace(archive=archive, region=region_file(tmp_path), min_zoom=0, max_zoom=2))

    assert "PASS" in capsys.readouterr().out


def rebuild_with_404(tmp_path, requests_mock, monkeypatch, archive):
    """Rebuild the fixture archive with one tile 404ing upstream - the
    absence export_dem.py tolerates and, since #659, declares in metadata."""
    requests_mock.get("https://dem.test/2/2/1.png", status_code=404)
    export_dem.main(
        argparse.Namespace(
            region=region_file(tmp_path),
            out=archive,
            min_zoom=0,
            max_zoom=2,
            quantize_step=0.5,
            workers=1,
            limit=0,
            name="test DEM",
        )
    )


def test_a_scattered_declared_source_absence_is_excused(tmp_path, requests_mock, monkeypatch):
    """#659: export_dem.py deliberately tolerates a tile the source lacks,
    and this gate used to hard-fail on it - one genuinely-missing AWS tile
    made the archive permanently unshippable. An absence the exporter
    itself declared is now excused. (The share ceiling is raised here only
    because the fixture region is a handful of tiles, so one absence is a
    quarter of it - real regions are tens of thousands.)"""
    archive = build_archive(tmp_path, requests_mock, monkeypatch)
    rebuild_with_404(tmp_path, requests_mock, monkeypatch, archive)
    monkeypatch.setattr(check_dem_archive, "MAX_ABSENT_SHARE", 0.5)

    assert check(archive, tmp_path) == []


def test_mass_declared_absence_reads_as_a_source_outage(tmp_path, requests_mock, monkeypatch):
    """The declaration is not a blank cheque: whole percents of a region
    absent at once means the source was down during the build, and the
    default MAX_ABSENT_SHARE refuses it however honestly it was declared."""
    archive = build_archive(tmp_path, requests_mock, monkeypatch)
    rebuild_with_404(tmp_path, requests_mock, monkeypatch, archive)

    problems = check(archive, tmp_path)

    assert any("over the" in p and "ceiling" in p for p in problems)


def test_fails_on_an_undeclared_missing_tile(tmp_path):
    """A tile absent with NO declaration is a hole - lost in transit or a
    truncated build - and stays exactly as fatal as it always was."""
    archive = hand_built_archive(tmp_path, [((0, 0, 0), webp_tile())])

    problems = check(archive, tmp_path, min_zoom=0, max_zoom=1)

    assert any("no declared source absence" in p and "1/1/0" in p for p in problems)


def test_fails_when_the_header_zoom_range_disagrees(tmp_path, requests_mock, monkeypatch):
    archive = build_archive(tmp_path, requests_mock, monkeypatch)

    problems = check(archive, tmp_path, min_zoom=0, max_zoom=3)

    assert any("header zoom range" in p for p in problems)


def webp_tile() -> bytes:
    buf = io.BytesIO()
    Image.fromarray(np.zeros((256, 256, 3), dtype=np.uint8)).save(buf, format="WEBP", lossless=True)
    return buf.getvalue()


def hand_built_archive(tmp_path, tiles, metadata=None):
    """A z0-only archive written directly, so a test can plant exactly the
    defect it is about."""
    out = tmp_path / "hand.pmtiles"
    with write(str(out)) as writer:
        for (z, x, y), data in tiles:
            writer.write_tile(zxy_to_tileid(z, x, y), data)
        header = build_header(NE_QUADRANT_BOX, 0)
        writer.finalize(
            header,
            metadata if metadata is not None else {"encoding": "terrarium", "quantize_step_m": 0.5},
        )
    return out


def test_fails_on_a_tile_that_is_not_a_256px_webp(tmp_path):
    png = terrarium_png(np.full((256, 256), 10.0))  # right size, wrong format
    archive = hand_built_archive(tmp_path, [((0, 0, 0), png)])

    problems = check(archive, tmp_path, min_zoom=0, max_zoom=0)

    assert any("not a valid 256px WebP" in p for p in problems)


def test_fails_on_a_tile_outside_the_region_walk(tmp_path):
    # z1 tile (0, 1) is the south-west quadrant - nowhere near the NE box.
    archive = hand_built_archive(
        tmp_path,
        [((0, 0, 0), webp_tile()), ((1, 1, 0), webp_tile()), ((1, 0, 1), webp_tile())],
    )

    problems = check(archive, tmp_path, min_zoom=0, max_zoom=1)

    assert any("outside the region walk" in p for p in problems)


def test_fails_when_the_terrarium_metadata_is_missing(tmp_path):
    archive = hand_built_archive(tmp_path, [((0, 0, 0), webp_tile())], metadata={"name": "mystery"})

    problems = check(archive, tmp_path, min_zoom=0, max_zoom=0)

    assert any("encoding" in p for p in problems)
    assert any("quantize_step_m" in p for p in problems)


def test_main_exits_nonzero_and_names_every_problem(tmp_path, capsys):
    archive = hand_built_archive(tmp_path, [((0, 0, 0), webp_tile())], metadata={})

    with pytest.raises(SystemExit):
        check_dem_archive.main(argparse.Namespace(archive=archive, region=region_file(tmp_path), min_zoom=0, max_zoom=0))

    assert "FAIL" in capsys.readouterr().out


def test_header_checks_cover_tile_type_and_compression():
    """The client decodes these via the browser's image decoder; TileType and
    Compression drifting from WEBP/NONE would render as no terrain. Pinned
    here as enum values so the check and the exporter cannot drift apart."""
    header = build_header(NE_QUADRANT_BOX, 0)

    assert header["tile_type"] == TileType.WEBP
    assert header["tile_compression"] == Compression.NONE


def test_quantize_unit_agrees_with_the_exporters():
    assert quantize_unit(0.5) == 128
