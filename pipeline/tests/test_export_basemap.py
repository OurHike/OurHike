"""Tests for export_basemap.py - the "build once" half of BASEMAP.md.

The external tools (osmium, Planetiler) are exercised through the command
builders, not run: the builders are the part this repo owns and can get
wrong quietly, while the tools themselves fail loudly in CI if an argument
name drifts. The end-to-end clip+merge path IS run where osmium exists,
against a synthetic corridor - the same fixture philosophy as the rest of
this suite (see conftest.py)."""

import argparse
import json
import shutil
import subprocess
from pathlib import Path

import pytest
from pmtiles.tile import Compression, TileType, zxy_to_tileid
from pmtiles.writer import write

import export_basemap
from export_basemap import (
    AT_STATES,
    fetch_states,
    osmium_extract_cmd,
    osmium_merge_cmd,
    planetiler_cmd,
    report_archive,
    state_urls,
)


def test_the_default_state_list_is_the_fourteen_at_states_with_no_duplicates():
    assert len(AT_STATES) == 14
    assert len(set(AT_STATES)) == 14
    # Endpoints as spot checks - a reordering is fine, a disappearance is not.
    assert "georgia" in AT_STATES and "maine" in AT_STATES


def test_state_urls_point_at_geofabrik_state_extracts():
    urls = dict(state_urls(["georgia", "maine"]))
    assert urls["georgia"] == "https://download.geofabrik.de/north-america/us/georgia-latest.osm.pbf"
    assert urls["maine"] == "https://download.geofabrik.de/north-america/us/maine-latest.osm.pbf"


def test_osmium_commands_clip_then_merge():
    extract = osmium_extract_cmd(Path("in.pbf"), Path("clip.poly"), Path("out.pbf"))
    assert extract[:2] == ["osmium", "extract"]
    assert "--polygon" in extract and "clip.poly" in extract

    merge = osmium_merge_cmd([Path("a.pbf"), Path("b.pbf")], Path("merged.pbf"))
    assert merge[:2] == ["osmium", "merge"]
    assert merge[-2:] == ["a.pbf", "b.pbf"]


def test_planetiler_command_carries_the_clip_polygon_only_when_given():
    clipped = planetiler_cmd(Path("p.jar"), Path("in.pbf"), Path("out.pmtiles"), 14, Path("clip.poly"), Path("tmp"))
    assert clipped[:3] == ["java", "-jar", "p.jar"]
    assert "--polygon=clip.poly" in clipped
    assert "--maxzoom=14" in clipped
    assert "--osm-path=in.pbf" in clipped
    assert "--output=out.pmtiles" in clipped

    unclipped = planetiler_cmd(Path("p.jar"), Path("in.pbf"), Path("out.pmtiles"), 14, None, Path("tmp"))
    assert not any(arg.startswith("--polygon") for arg in unclipped)


def test_layer_stats_are_asked_for_only_when_wanted():
    """Planetiler logs a `layer_stats` path whether or not it writes one, so
    the file's absence is the only way to find out it was never requested -
    which is exactly how the first shard-seam run failed. The flag is what
    actually produces it."""
    default = planetiler_cmd(Path("p.jar"), Path("in.pbf"), Path("out.pmtiles"), 14, None, Path("tmp"))
    assert "--output-layerstats" not in default

    asked = planetiler_cmd(Path("p.jar"), Path("in.pbf"), Path("out.pmtiles"), 14, None, Path("tmp"), layer_stats=True)
    assert "--output-layerstats" in asked


def test_fetch_states_skips_files_already_present(tmp_path, requests_mock):
    (tmp_path / "georgia-latest.osm.pbf").write_bytes(b"already here")
    requests_mock.get(
        "https://download.geofabrik.de/north-america/us/maine-latest.osm.pbf",
        content=b"maine bytes",
    )

    paths = fetch_states(["georgia", "maine"], tmp_path)

    assert [p.name for p in paths] == ["georgia-latest.osm.pbf", "maine-latest.osm.pbf"]
    assert (tmp_path / "georgia-latest.osm.pbf").read_bytes() == b"already here"
    assert (tmp_path / "maine-latest.osm.pbf").read_bytes() == b"maine bytes"
    assert requests_mock.call_count == 1, "the present file must not be re-fetched"


def test_report_archive_counts_tiles_and_bytes_per_zoom(tmp_path, capsys):
    path = tmp_path / "tiny.pmtiles"
    header = {
        "tile_type": TileType.MVT,
        "tile_compression": Compression.NONE,
        "min_lon_e7": 0,
        "min_lat_e7": 0,
        "max_lon_e7": 0,
        "max_lat_e7": 0,
        "center_lon_e7": 0,
        "center_lat_e7": 0,
        "center_zoom": 0,
    }
    with write(str(path)) as writer:
        writer.write_tile(zxy_to_tileid(0, 0, 0), b"four")
        writer.write_tile(zxy_to_tileid(1, 0, 0), b"eight...")
        writer.write_tile(zxy_to_tileid(1, 1, 0), b"12 bytes....")
        writer.finalize(header, {"name": "tiny"})

    per_zoom = report_archive(path)

    assert per_zoom == {0: (1, 4), 1: (2, 20)}
    out = capsys.readouterr().out
    assert "tiny.pmtiles" in out and "zoom" in out


def test_no_clip_over_the_full_default_state_list_is_refused():
    args = argparse.Namespace(no_clip=True, states=AT_STATES, planetiler_jar=None, refetch=False, max_zoom=14, out=Path("x"))
    with pytest.raises(SystemExit, match="machine sized for it"):
        export_basemap.main(args)


@pytest.mark.skipif(shutil.which("osmium") is None, reason="osmium-tool not installed (CI installs it)")
def test_main_clips_and_merges_a_synthetic_state_end_to_end(tmp_path, monkeypatch):
    """main() through the shapes -> clip -> merge path against a tiny
    synthetic corridor and a tiny synthetic 'state', stopping where the
    Planetiler jar would take over. This is the test that proves the shapes
    main() writes are the shapes the real osmium accepts.

    The corridor is stubbed with a plain shapely buffer rather than built
    through DuckDB: lib/corridor.py has its own tests, and what is under
    test here is main()'s orchestration of the shapes and tools, not the
    buffer SQL."""
    from shapely.geometry import LineString

    corridor = LineString([(-74.05, 41.05), (-74.00, 41.10)]).buffer(0.5)
    monkeypatch.setattr(export_basemap, "load_corridor_4326", lambda: corridor)

    raw_dir = tmp_path / "osm"
    out_dir = tmp_path / "processed"
    monkeypatch.setattr(export_basemap, "OSM_RAW_DIR", raw_dir)
    monkeypatch.setattr(export_basemap, "OUT_DIR", out_dir)
    monkeypatch.setattr(export_basemap, "CLIP_POLY_PATH", raw_dir / "clip.poly")
    monkeypatch.setattr(export_basemap, "REGION_PATH", out_dir / "basemap_region.geojson")

    def fake_fetch(states, dest_dir, refetch=False):
        # One "state": a node on the centerline (inside any 30-mile buffer)
        # and one on the far side of the continent, so the clip has something
        # real to drop. Converted to PBF by the same osmium the test needs.
        xml = dest_dir / "testonia.osm"
        dest_dir.mkdir(parents=True, exist_ok=True)
        xml.write_text(
            """<?xml version='1.0' encoding='UTF-8'?>
<osm version="0.6" generator="test">
  <node id="1" version="1" lat="41.05" lon="-74.05"/>
  <node id="2" version="1" lat="45.00" lon="-120.00"/>
</osm>
"""
        )
        pbf = dest_dir / "testonia-latest.osm.pbf"
        subprocess.run(["osmium", "cat", "--overwrite", "-o", str(pbf), str(xml)], check=True, capture_output=True)
        return [pbf]

    monkeypatch.setattr(export_basemap, "fetch_states", fake_fetch)

    args = argparse.Namespace(
        states=["testonia"], planetiler_jar=None, max_zoom=14, out=out_dir / "basemap.pmtiles", refetch=False, no_clip=False
    )
    export_basemap.main(args)

    assert (raw_dir / "clip.poly").exists()
    region = json.loads((out_dir / "basemap_region.geojson").read_text())
    assert region["geometry"]["type"] in ("Polygon", "MultiPolygon")

    merged = raw_dir / "basemap-input.osm.pbf"
    assert merged.exists()
    kept = subprocess.run(["osmium", "cat", str(merged), "-f", "osm"], check=True, capture_output=True, text=True).stdout
    assert 'id="1"' in kept, "the node inside the corridor must survive"
    assert 'id="2"' not in kept, "the node outside the corridor must be clipped"


def test_the_http_timeout_is_only_sent_when_raised():
    """Planetiler's own default is 30s and that is usually right; the spike
    raises it because the profile's 1.4 GB of third-party sources timed out
    twice mid-measurement."""
    default = planetiler_cmd(Path("p.jar"), Path("in.pbf"), Path("out.pmtiles"), 14, None, Path("tmp"))
    assert not any(arg.startswith("--http-timeout") for arg in default)

    patient = planetiler_cmd(Path("p.jar"), Path("in.pbf"), Path("out.pmtiles"), 14, None, Path("tmp"), http_timeout_seconds=300)
    assert "--http-timeout=300s" in patient
