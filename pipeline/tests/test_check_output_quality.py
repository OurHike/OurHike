"""Tests for check_output_quality.py - "did the pipeline actually produce
complete, correct output?", checked after export and before publish.

See that module's own docstring for the full reasoning behind each of its
four checks (most notably check #2, the corridor cross-check, whose real
value only makes sense once you know every consumer now builds the
corridor fresh rather than reading a stale committed file). Small synthetic
fixtures throughout - tiny GeoJSON/GeoTIFF built in test code, never real
pipeline output - per TESTING.md.
"""

import json
from datetime import datetime, timedelta, timezone

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_bounds

import check_output_quality
import check_water_reach
from check_output_quality import Verdict
from lib import fetch_receipts
from tests.synthetic import write_centerline

# --- Shared fixtures ---------------------------------------------------------


def _write_tiny_geotiff(path):
    """Same tiny-fixture shape test_fetch_topo_quads.py's own
    _write_tiny_geotiff() uses - duplicated here rather than imported across
    test modules, per this project's small-synthetic-fixture-in-test-code
    convention (see TESTING.md)."""
    transform = from_bounds(-74.1, 41.0, -74.0, 41.1, 4, 4)
    profile = {
        "driver": "GTiff",
        "height": 4,
        "width": 4,
        "count": 1,
        "dtype": "uint8",
        "crs": "EPSG:4326",
        "transform": transform,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(np.full((1, 4, 4), 100, dtype="uint8"))


def _artifact_entry(path, content, feature_count):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return {"path": str(path), "sha256": check_output_quality.sha256_file(path), "feature_count": feature_count}


# --- sha256_file / read_manifest / artifact_problems ------------------------


def test_read_manifest_returns_none_when_the_file_does_not_exist(tmp_path):
    assert check_output_quality.read_manifest(tmp_path / "absent.json") is None


def test_read_manifest_loads_the_json_file(tmp_path):
    path = tmp_path / "m.json"
    path.write_text(json.dumps({"a": 1}))

    assert check_output_quality.read_manifest(path) == {"a": 1}


def test_artifact_problems_flags_a_missing_path_field():
    assert check_output_quality.artifact_problems("x", {}) == ["x: manifest entry has no path"]


def test_artifact_problems_flags_a_file_missing_from_disk(tmp_path):
    entry = {"path": str(tmp_path / "gone.geojson"), "sha256": "whatever"}

    problems = check_output_quality.artifact_problems("x", entry)

    assert len(problems) == 1
    assert "file missing on disk" in problems[0]


def test_artifact_problems_flags_a_sha256_mismatch(tmp_path):
    """The real independent check this module exists to add: the manifest
    can say whatever it wants, this re-hashes the actual file."""
    path = tmp_path / "trails.geojson"
    path.write_text("real content")
    entry = {"path": str(path), "sha256": "0" * 64}

    problems = check_output_quality.artifact_problems("x", entry)

    assert len(problems) == 1
    assert "sha256 mismatch" in problems[0]


def test_artifact_problems_is_empty_when_the_file_matches_the_manifest(tmp_path):
    path = tmp_path / "trails.geojson"
    path.write_text("real content")
    entry = {"path": str(path), "sha256": check_output_quality.sha256_file(path)}

    assert check_output_quality.artifact_problems("x", entry) == []


# --- summarise ----------------------------------------------------------------


def _report(**verdicts):
    return [
        {"check": name, "verdict": verdict, "problems": [f"{name} problem"] if verdict is Verdict.PROBLEM else []}
        for name, verdict in verdicts.items()
    ]


def test_summarise_is_clean_when_everything_is_ok():
    summary = check_output_quality.summarise(_report(trails=Verdict.OK, poi=Verdict.OK))

    assert summary["failed_checks"] == []
    assert summary["exit_code"] == 0


def test_summarise_names_exactly_which_checks_failed():
    summary = check_output_quality.summarise(_report(trails=Verdict.PROBLEM, poi=Verdict.OK))

    assert summary["failed_checks"] == ["trails"]
    assert summary["problems"]["trails"] == ["trails problem"]


def test_summarise_exit_code_is_nonzero_when_any_check_has_a_problem():
    assert check_output_quality.summarise(_report(trails=Verdict.PROBLEM))["exit_code"] != 0


def test_summarise_separates_skipped_from_failed():
    summary = check_output_quality.summarise(_report(topo_quads=Verdict.SKIPPED, trails=Verdict.PROBLEM))

    assert summary["skipped"] == ["topo_quads"]
    assert summary["failed_checks"] == ["trails"]


def test_summarise_skipped_alone_does_not_gate_the_exit_code():
    """Nothing was produced yet for a SKIPPED check to evaluate - a
    different situation from evaluating something and finding it wrong, so
    it must not fail the run on its own."""
    summary = check_output_quality.summarise(_report(topo_quads=Verdict.SKIPPED, baseline=Verdict.SKIPPED))

    assert summary["exit_code"] == 0


# --- Check 1: trails_verdict --------------------------------------------------


def test_trails_verdict_is_problem_when_manifest_is_missing(tmp_path):
    report = check_output_quality.trails_verdict(tmp_path / "absent.json")

    assert report["verdict"] is Verdict.PROBLEM
    assert report["counts"] == {}


def test_trails_verdict_ok_for_a_complete_matching_manifest(tmp_path):
    manifest_path = tmp_path / "trails_manifest.json"
    manifest = {
        "geojson": _artifact_entry(tmp_path / "trails.geojson", "geojson bytes", 10),
        "fgb": _artifact_entry(tmp_path / "trails.fgb", "fgb bytes", 10),
    }
    manifest_path.write_text(json.dumps(manifest))

    report = check_output_quality.trails_verdict(manifest_path)

    assert report["verdict"] is Verdict.OK
    assert report["problems"] == []
    assert report["counts"] == {"trails": 10}


def test_trails_verdict_flags_a_zero_feature_count(tmp_path):
    manifest_path = tmp_path / "trails_manifest.json"
    manifest = {
        "geojson": _artifact_entry(tmp_path / "trails.geojson", "geojson bytes", 0),
        "fgb": _artifact_entry(tmp_path / "trails.fgb", "fgb bytes", 0),
    }
    manifest_path.write_text(json.dumps(manifest))

    report = check_output_quality.trails_verdict(manifest_path)

    assert report["verdict"] is Verdict.PROBLEM
    assert any("trails: 0" in p for p in report["problems"])


def test_trails_verdict_flags_a_sha256_mismatch_against_the_real_file_on_disk(tmp_path):
    """The independent second check this module exists to add: a manifest
    written by a passing export_trails.py run whose artifact file was
    edited/corrupted/truncated afterwards must not read as OK just because
    the recorded feature_count still looks fine."""
    manifest_path = tmp_path / "trails_manifest.json"
    entry = _artifact_entry(tmp_path / "trails.geojson", "original content", 10)
    (tmp_path / "trails.geojson").write_text("tampered content")  # changes on disk after the manifest was written
    manifest = {"geojson": entry, "fgb": _artifact_entry(tmp_path / "trails.fgb", "fgb bytes", 10)}
    manifest_path.write_text(json.dumps(manifest))

    report = check_output_quality.trails_verdict(manifest_path)

    assert report["verdict"] is Verdict.PROBLEM
    assert any("sha256 mismatch" in p for p in report["problems"])


def test_trails_verdict_flags_a_kind_missing_from_an_otherwise_present_manifest(tmp_path):
    manifest_path = tmp_path / "trails_manifest.json"
    manifest_path.write_text(json.dumps({"geojson": _artifact_entry(tmp_path / "trails.geojson", "geojson bytes", 10)}))

    report = check_output_quality.trails_verdict(manifest_path)

    assert report["verdict"] is Verdict.PROBLEM
    assert any("trails.fgb" in p and "missing" in p for p in report["problems"])


def test_trails_verdict_tracks_the_pre_merge_segment_count_when_the_manifest_records_one(tmp_path):
    """#161: ~3,000 centerline segments merged into ~500 chains changed what
    feature_count means, and the baseline drop-detector comparing chain
    counts to segment counts would read the merge itself as a broken export.
    The manifest records `constituent_count` (per-segment, pre-merge), and
    that is the number completeness and the baseline track - it stays
    continuous across the merge while still moving when an upstream really
    loses segments. A manifest from before the merge has no such field and
    falls back to feature_count, exactly as before."""
    manifest_path = tmp_path / "trails_manifest.json"
    manifest = {
        "geojson": _artifact_entry(tmp_path / "trails.geojson", "geojson bytes", 500),
        "fgb": _artifact_entry(tmp_path / "trails.fgb", "fgb bytes", 500),
        "constituent_count": 4224,
    }
    manifest_path.write_text(json.dumps(manifest))

    report = check_output_quality.trails_verdict(manifest_path)

    assert report["verdict"] is Verdict.OK
    assert report["counts"] == {"trails": 4224}
    assert "500 features (4224 constituent segments)" in report["detail"]


def test_trails_verdict_flags_geojson_fgb_feature_count_disagreement(tmp_path):
    manifest_path = tmp_path / "trails_manifest.json"
    manifest = {
        "geojson": _artifact_entry(tmp_path / "trails.geojson", "geojson bytes", 10),
        "fgb": _artifact_entry(tmp_path / "trails.fgb", "fgb bytes", 9),
    }
    manifest_path.write_text(json.dumps(manifest))

    report = check_output_quality.trails_verdict(manifest_path)

    assert report["verdict"] is Verdict.PROBLEM
    assert any("disagree" in p for p in report["problems"])


# --- Check 1: poi_verdict ------------------------------------------------------


def _poi_manifest(tmp_path, counts: dict) -> dict:
    manifest = {}
    for poi_type in check_output_quality.POI_TYPES:
        count = counts.get(poi_type, 5)
        manifest[poi_type] = {
            "geojson": _artifact_entry(tmp_path / f"{poi_type}.geojson", f"{poi_type} geojson", count),
            "fgb": _artifact_entry(tmp_path / f"{poi_type}.fgb", f"{poi_type} fgb", count),
        }
    return manifest


def test_poi_verdict_is_problem_when_manifest_is_missing(tmp_path):
    report = check_output_quality.poi_verdict(tmp_path / "absent.json")

    assert report["verdict"] is Verdict.PROBLEM


def test_poi_verdict_ok_when_every_type_has_features_except_crossing(tmp_path):
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(_poi_manifest(tmp_path, {"crossing": 0})))

    report = check_output_quality.poi_verdict(manifest_path)

    assert report["verdict"] is Verdict.OK
    assert report["counts"]["poi:crossing"] == 0
    assert report["counts"]["poi:shelter"] == 5


def test_poi_verdict_flags_a_zero_count_poi_type_other_than_crossing(tmp_path):
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(_poi_manifest(tmp_path, {"crossing": 0, "shelter": 0})))

    report = check_output_quality.poi_verdict(manifest_path)

    assert report["verdict"] is Verdict.PROBLEM
    assert any("poi:shelter" in p for p in report["problems"])


def test_poi_verdict_does_not_flag_crossing_at_zero():
    """Mirrors export_poi.py's own minimums={"crossing": 0} - there is no
    NHD-crossing fetch script yet, so an empty crossing layer is expected,
    not a bug."""
    problems = check_output_quality.count_problems({"poi:crossing": 0, "poi:shelter": 5}, minimums={"poi:crossing": 0})

    assert problems == []


def test_poi_verdict_flags_a_kind_missing_within_an_otherwise_present_poi_type(tmp_path):
    manifest = _poi_manifest(tmp_path, {"crossing": 0})
    del manifest["shelter"]["fgb"]
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest))

    report = check_output_quality.poi_verdict(manifest_path)

    assert report["verdict"] is Verdict.PROBLEM
    assert any("poi.shelter.fgb" in p and "missing" in p for p in report["problems"])


def test_poi_verdict_flags_geojson_fgb_feature_count_disagreement_for_one_poi_type(tmp_path):
    manifest = _poi_manifest(tmp_path, {"crossing": 0})
    manifest["shelter"]["fgb"]["feature_count"] = 4  # geojson stayed at 5 - a real write-path bug would look like this
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest))

    report = check_output_quality.poi_verdict(manifest_path)

    assert report["verdict"] is Verdict.PROBLEM
    assert any("poi.shelter" in p and "disagree" in p for p in report["problems"])


def test_poi_verdict_flags_a_poi_type_missing_from_the_manifest_entirely(tmp_path):
    manifest = _poi_manifest(tmp_path, {})
    del manifest["water"]
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest))

    report = check_output_quality.poi_verdict(manifest_path)

    assert report["verdict"] is Verdict.PROBLEM
    assert any("poi.water" in p and "missing" in p for p in report["problems"])


# --- Check 1: elevation_verdict ------------------------------------------------


def test_elevation_verdict_is_problem_when_manifest_is_missing(tmp_path):
    report = check_output_quality.elevation_verdict(tmp_path / "absent.json")

    assert report["verdict"] is Verdict.PROBLEM


def test_elevation_verdict_ok_for_a_nonzero_point_count(tmp_path):
    entry = _artifact_entry(tmp_path / "elevation_profile.json", "profile bytes", 0)
    entry["point_count"] = entry.pop("feature_count")
    manifest_path = tmp_path / "elevation_manifest.json"
    manifest_path.write_text(json.dumps({**entry, "point_count": 139219}))

    report = check_output_quality.elevation_verdict(manifest_path)

    assert report["verdict"] is Verdict.OK
    assert report["counts"] == {"elevation": 139219}


def test_elevation_verdict_flags_a_zero_point_count(tmp_path):
    entry = _artifact_entry(tmp_path / "elevation_profile.json", "profile bytes", 0)
    manifest_path = tmp_path / "elevation_manifest.json"
    manifest_path.write_text(json.dumps({"path": entry["path"], "sha256": entry["sha256"], "point_count": 0}))

    report = check_output_quality.elevation_verdict(manifest_path)

    assert report["verdict"] is Verdict.PROBLEM


def test_elevation_verdict_includes_null_elevation_pct_in_the_detail_when_present(tmp_path):
    entry = _artifact_entry(tmp_path / "elevation_profile.json", "profile bytes", 0)
    manifest_path = tmp_path / "elevation_manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "path": entry["path"],
                "sha256": entry["sha256"],
                "point_count": 100,
                "null_elevation_count": 3,
                "null_elevation_pct": 3.0,
            }
        )
    )

    report = check_output_quality.elevation_verdict(manifest_path)

    assert report["verdict"] is Verdict.OK
    assert "3.0%" in report["detail"]


def test_elevation_verdict_works_without_null_elevation_pct_for_an_older_manifest(tmp_path):
    """Real-data gotcha found while building this module: the local
    elevation_manifest.json on disk right now predates null_elevation_pct
    being added to export_elevation.py's manifest (it has never been
    regenerated since, since a full run is intentionally manual-only - see
    that script's docstring). A manifest missing this newer field entirely
    must still work, not just one that has it set to null."""
    entry = _artifact_entry(tmp_path / "elevation_profile.json", "profile bytes", 0)
    manifest_path = tmp_path / "elevation_manifest.json"
    manifest_path.write_text(json.dumps({"path": entry["path"], "sha256": entry["sha256"], "point_count": 139219}))

    report = check_output_quality.elevation_verdict(manifest_path)

    assert report["verdict"] is Verdict.OK
    assert "139219 points" in report["detail"]


# --- Check 1: spurs_verdict ----------------------------------------------------


def test_spurs_verdict_is_problem_when_manifest_is_missing(tmp_path):
    """Until #172 spurs.json was the only published artifact with no verdict
    here at all - a truncated or empty file shipped with every check green."""
    report = check_output_quality.spurs_verdict(tmp_path / "absent.json")

    assert report["verdict"] is Verdict.PROBLEM
    assert report["reason"] == check_output_quality.MANIFEST_MISSING


def test_spurs_verdict_ok_for_a_nonzero_spur_count(tmp_path):
    entry = _artifact_entry(tmp_path / "spurs.json", "spur bytes", 0)
    manifest_path = tmp_path / "spurs_manifest.json"
    manifest_path.write_text(
        json.dumps({"path": entry["path"], "sha256": entry["sha256"], "spur_count": 62, "resolved_count": 41})
    )

    report = check_output_quality.spurs_verdict(manifest_path)

    assert report["verdict"] is Verdict.OK
    assert report["counts"] == {"spurs": 62}
    assert "41 with a destination" in report["detail"]


def test_spurs_verdict_flags_a_zero_spur_count(tmp_path):
    """An empty spurs.json has so far only ever meant a decode or input
    failure upstream, so zero fails rather than publishing quietly."""
    entry = _artifact_entry(tmp_path / "spurs.json", "spur bytes", 0)
    manifest_path = tmp_path / "spurs_manifest.json"
    manifest_path.write_text(json.dumps({"path": entry["path"], "sha256": entry["sha256"], "spur_count": 0}))

    report = check_output_quality.spurs_verdict(manifest_path)

    assert report["verdict"] is Verdict.PROBLEM


def test_spurs_verdict_flags_an_artifact_that_drifted_from_its_manifest(tmp_path):
    entry = _artifact_entry(tmp_path / "spurs.json", "spur bytes", 0)
    (tmp_path / "spurs.json").write_text("tampered after hashing")
    manifest_path = tmp_path / "spurs_manifest.json"
    manifest_path.write_text(json.dumps({"path": entry["path"], "sha256": entry["sha256"], "spur_count": 62}))

    report = check_output_quality.spurs_verdict(manifest_path)

    assert report["verdict"] is Verdict.PROBLEM
    assert any("sha256 mismatch" in p for p in report["problems"])


# --- manifests_verdict (#659) --------------------------------------------------


def test_manifests_verdict_verifies_club_sections_and_present_stretch_manifests(tmp_path):
    club_manifest = tmp_path / "club_sections_manifest.json"
    club_entry = _artifact_entry(tmp_path / "club_sections.json", "club bytes", 0)
    club_manifest.write_text(json.dumps({"path": club_entry["path"], "sha256": club_entry["sha256"]}))

    stretch_entry = _artifact_entry(tmp_path / "at_basemap_stretch_00.pmtiles", "stretch bytes", 0)
    (tmp_path / "at_basemap_stretches_manifest.json").write_text(
        json.dumps({"artifacts": {"at_basemap_stretch_00.pmtiles": stretch_entry}})
    )

    report = check_output_quality.manifests_verdict(club_manifest_path=club_manifest, stretches_dir=tmp_path)

    assert report["verdict"] is Verdict.OK
    assert report["problems"] == []


def test_manifests_verdict_flags_a_stretch_artifact_that_drifted_from_its_manifest(tmp_path):
    """The audited gap: publish.py trusts these manifests' hashes across the
    time gap since the cut, and nothing re-verified them (#659)."""
    club_manifest = tmp_path / "club_sections_manifest.json"
    club_entry = _artifact_entry(tmp_path / "club_sections.json", "club bytes", 0)
    club_manifest.write_text(json.dumps({"path": club_entry["path"], "sha256": club_entry["sha256"]}))

    stretch_entry = _artifact_entry(tmp_path / "dem_stretch_03.pmtiles", "original bytes", 0)
    (tmp_path / "dem_stretches_manifest.json").write_text(json.dumps({"artifacts": {"dem_stretch_03.pmtiles": stretch_entry}}))
    (tmp_path / "dem_stretch_03.pmtiles").write_text("rebuilt after the manifest recorded its hash")

    report = check_output_quality.manifests_verdict(club_manifest_path=club_manifest, stretches_dir=tmp_path)

    assert report["verdict"] is Verdict.PROBLEM
    assert any("dem_stretch_03" in p for p in report["problems"])


def test_manifests_verdict_treats_a_missing_club_manifest_as_an_excusable_problem(tmp_path):
    report = check_output_quality.manifests_verdict(club_manifest_path=tmp_path / "absent.json", stretches_dir=tmp_path)

    assert report["verdict"] is Verdict.PROBLEM
    assert report["reason"] == check_output_quality.MANIFEST_MISSING, (
        "missing means never-built, which is exactly what --optional manifests exists to excuse"
    )


def test_manifests_verdict_does_not_fail_a_vector_run_for_having_no_stretches(tmp_path):
    """Stretch archives exist only after a basemap/dem build; their absence
    on a vector-only run is normal and must be noted, not failed."""
    club_manifest = tmp_path / "club_sections_manifest.json"
    club_entry = _artifact_entry(tmp_path / "club_sections.json", "club bytes", 0)
    club_manifest.write_text(json.dumps({"path": club_entry["path"], "sha256": club_entry["sha256"]}))

    report = check_output_quality.manifests_verdict(club_manifest_path=club_manifest, stretches_dir=tmp_path)

    assert report["verdict"] is Verdict.OK
    assert "not built this run" in report["detail"]


# --- Check 6: water_reach_verdict ---------------------------------------------
#
# What a point being past the gate MEANS is test_check_water_reach.py's subject,
# on its own geometry. These are about this module's contract: which verdict a
# given state of data/processed/ produces, and that a skip is never a pass.


def _water_tree(tmp_path, water_features, centerline=None):
    """A data/processed water layer and the data/raw layers it is measured
    against, in the two shapes check_water_reach.processed_paths() names."""
    raw = tmp_path / "raw"
    processed = tmp_path / "processed" / "poi"
    raw.mkdir(parents=True, exist_ok=True)
    processed.mkdir(parents=True, exist_ok=True)

    write_centerline(raw / "centerline.geojson", *([centerline] if centerline is not None else []))
    for empty in ("side_trails.geojson", "shelters.geojson", "campsites.geojson"):
        (raw / empty).write_text(json.dumps({"type": "FeatureCollection", "features": []}))

    water_path = processed / "water.geojson"
    water_path.write_text(json.dumps({"type": "FeatureCollection", "features": water_features}))
    return raw, water_path


def _osm_water(lon, lat):
    return {
        "type": "Feature",
        "properties": {"id": "osm_water:1", "poi_type": "water", "source": "osm_water"},
        "geometry": {"type": "Point", "coordinates": [lon, lat]},
    }


def test_water_reach_verdict_passes_water_a_hiker_can_walk_to(tmp_path, monkeypatch):
    raw, water_path = _water_tree(tmp_path, [_osm_water(-74.0, 41.0)])
    monkeypatch.setattr(check_water_reach, "RAW_DIR", raw)

    report = check_output_quality.water_reach_verdict(water_path)

    assert report["verdict"] is Verdict.OK
    assert report["problems"] == []


def test_water_reach_verdict_flags_a_point_no_hiker_could_reach(tmp_path, monkeypatch):
    """The failure #916 exists for, in the one place that can stop it reaching
    the bucket: this runs before publish.py."""
    far = 41.0 + 3000.0 / 111_132.0
    raw, water_path = _water_tree(tmp_path, [_osm_water(-74.0, far)])
    monkeypatch.setattr(check_water_reach, "RAW_DIR", raw)

    report = check_output_quality.water_reach_verdict(water_path)

    assert report["verdict"] is Verdict.PROBLEM
    assert "osm_water:1" in report["problems"][0]
    assert "1 of 1 past the gate" in report["detail"]


def test_water_reach_verdict_skips_when_no_water_was_exported(tmp_path, monkeypatch):
    """publish.py supports partial publishes, and a run that exported no POIs
    has nothing here to be wrong about."""
    raw, _ = _water_tree(tmp_path, [])
    monkeypatch.setattr(check_water_reach, "RAW_DIR", raw)

    report = check_output_quality.water_reach_verdict(tmp_path / "processed" / "poi" / "absent.geojson")

    assert report["verdict"] is Verdict.SKIPPED
    assert report["problems"] == []


def test_water_reach_verdict_passes_a_water_layer_with_no_osm_points(tmp_path, monkeypatch):
    """Every release before #529 added the source. A pass and not a skip -
    there was something to check and nothing was wrong with it."""
    opentrail = {
        "type": "Feature",
        "properties": {"id": "opentrail_at:1", "poi_type": "water", "source": "opentrail_at"},
        "geometry": {"type": "Point", "coordinates": [-74.0, 41.0]},
    }
    raw, water_path = _water_tree(tmp_path, [opentrail])
    monkeypatch.setattr(check_water_reach, "RAW_DIR", raw)

    report = check_output_quality.water_reach_verdict(water_path)

    assert report["verdict"] is Verdict.OK
    assert report["detail"].startswith("0 osm_water")


def test_water_reach_verdict_crashing_is_a_problem_rather_than_silence(tmp_path, monkeypatch):
    """A gate in front of publish.py must never read as "nothing to report"
    because it fell over - _safe_verdict is what keeps that promise here."""

    def explode(*_args, **_kwargs):
        raise RuntimeError("synthetic failure")

    monkeypatch.setattr(check_water_reach, "check_reach", explode)
    _, water_path = _water_tree(tmp_path, [_osm_water(-74.0, 41.0)])

    report = check_output_quality._safe_verdict("water_reach", lambda: check_output_quality.water_reach_verdict(water_path))

    assert report["verdict"] is Verdict.PROBLEM
    assert "synthetic failure" in report["problems"][0]


# --- Check 2: corridor_verdict -------------------------------------------------


def test_corridor_verdict_is_problem_when_centerline_is_missing(tmp_path):
    report = check_output_quality.corridor_verdict(tmp_path / "absent.geojson")

    assert report["verdict"] is Verdict.PROBLEM
    assert "missing" in report["problems"][0]


def test_corridor_verdict_ok_for_a_real_centerline_fixture(tmp_path):
    spurs_manifest = tmp_path / "spurs_manifest.json"
    spurs_entry = _artifact_entry(tmp_path / "spurs.json", "spurs bytes", 0)
    spurs_manifest.write_text(
        json.dumps(
            {
                "path": spurs_entry["path"],
                "sha256": spurs_entry["sha256"],
                "spur_count": 62,
                "resolved_count": 41,
            }
        )
    )

    centerline_path = tmp_path / "centerline.geojson"
    write_centerline(centerline_path)

    report = check_output_quality.corridor_verdict(centerline_path)

    assert report["verdict"] is Verdict.OK
    assert report["problems"] == []


def test_corridor_verdict_flags_a_degenerate_corridor_for_an_empty_centerline(tmp_path):
    """Zero features means zero corridor area - a garbage-but-internally-
    consistent result the two-independent-builds-agree check alone would
    wave through, since both builds would agree with each other and both be
    empty. Confirmed empirically: build_corridor() over zero rows returns
    one row with area 0.0 and a null bbox, not an error."""
    centerline_path = tmp_path / "centerline.geojson"
    centerline_path.write_text(json.dumps({"type": "FeatureCollection", "features": []}))

    report = check_output_quality.corridor_verdict(centerline_path)

    assert report["verdict"] is Verdict.PROBLEM
    assert any("degenerate" in p for p in report["problems"])


def test_corridor_verdict_flags_area_disagreement_between_two_independent_builds(tmp_path, monkeypatch):
    """Proves the comparison logic actually has teeth: forces
    corridor_stats() to return two different results (standing in for real
    non-determinism, or centerline.geojson changing mid-run - see the
    module docstring) and confirms corridor_verdict() notices, rather than
    only ever comparing a value against itself."""
    centerline_path = tmp_path / "centerline.geojson"
    centerline_path.write_text("irrelevant - corridor_stats is faked below")
    results = iter(
        [
            {"area_sq_mi": 81000.0, "bbox": (-84.0, 34.0, -68.0, 46.0)},
            {"area_sq_mi": 90000.0, "bbox": (-84.0, 34.0, -68.0, 46.0)},
        ]
    )
    monkeypatch.setattr(check_output_quality, "corridor_stats", lambda path: next(results))

    report = check_output_quality.corridor_verdict(centerline_path)

    assert report["verdict"] is Verdict.PROBLEM
    assert any("disagree on area" in p for p in report["problems"])


def test_corridor_verdict_flags_bbox_disagreement_between_two_independent_builds(tmp_path, monkeypatch):
    centerline_path = tmp_path / "centerline.geojson"
    centerline_path.write_text("irrelevant - corridor_stats is faked below")
    results = iter(
        [
            {"area_sq_mi": 81000.0, "bbox": (-84.0, 34.0, -68.0, 46.0)},
            {"area_sq_mi": 81000.0, "bbox": (-84.5, 34.0, -68.0, 46.0)},
        ]
    )
    monkeypatch.setattr(check_output_quality, "corridor_stats", lambda path: next(results))

    report = check_output_quality.corridor_verdict(centerline_path)

    assert report["verdict"] is Verdict.PROBLEM
    assert any("bbox xmin" in p for p in report["problems"])


def test_corridor_verdict_is_problem_when_the_corridor_build_itself_raises(tmp_path, monkeypatch):
    centerline_path = tmp_path / "centerline.geojson"
    centerline_path.write_text("irrelevant - corridor_stats is faked below")

    def _raise(path):
        raise RuntimeError("synthetic DuckDB failure")

    monkeypatch.setattr(check_output_quality, "corridor_stats", _raise)

    report = check_output_quality.corridor_verdict(centerline_path)

    assert report["verdict"] is Verdict.PROBLEM
    assert "corridor build failed" in report["problems"][0]


def test_corridor_verdict_does_not_flag_two_builds_that_genuinely_agree(tmp_path, monkeypatch):
    centerline_path = tmp_path / "centerline.geojson"
    centerline_path.write_text("irrelevant - corridor_stats is faked below")
    stats = {"area_sq_mi": 81000.0, "bbox": (-84.0, 34.0, -68.0, 46.0)}
    monkeypatch.setattr(check_output_quality, "corridor_stats", lambda path: dict(stats))

    report = check_output_quality.corridor_verdict(centerline_path)

    assert report["verdict"] is Verdict.OK


# --- Check 3: topo_quads_verdict -----------------------------------------------


def _topo_entry(local_path):
    return {"last_modified": "Thu, 19 Sep 2024 21:20:18 GMT", "local_path": str(local_path)}


def test_topo_quads_verdict_is_skipped_when_manifest_is_missing(tmp_path):
    """SKIPPED, not PROBLEM: unlike trails/poi/elevation, this module's
    documented position (after the four EXPORT scripts) doesn't guarantee a
    FETCH-stage manifest exists yet."""
    report = check_output_quality.topo_quads_verdict(tmp_path / "absent.json")

    assert report["verdict"] is Verdict.SKIPPED


def test_topo_quads_verdict_ok_when_recorded_quads_exist_and_sample_is_readable(tmp_path):
    quad_path = tmp_path / "CT_Ansonia.tif"
    _write_tiny_geotiff(quad_path)
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps({"https://x/CT_Ansonia.tif": _topo_entry(quad_path)}))

    report = check_output_quality.topo_quads_verdict(manifest_path, sample_size=1)

    assert report["verdict"] is Verdict.OK
    assert report["problems"] == []


def test_topo_quads_verdict_flags_a_manifest_entry_whose_file_no_longer_exists(tmp_path):
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps({"https://x/gone.tif": _topo_entry(tmp_path / "gone.tif")}))

    report = check_output_quality.topo_quads_verdict(manifest_path, sample_size=1)

    assert report["verdict"] is Verdict.PROBLEM
    assert any("missing from disk" in p for p in report["problems"])


def test_topo_quads_verdict_flags_an_unreadable_quad_found_in_the_sample(tmp_path):
    """The actual independent value this backstop adds: a quad that passed
    fetch_topo_quads.py's own read-validation once, at download time, can
    still be found broken later (disk fault, interrupted copy) - this
    re-runs that same validation now."""
    bad_path = tmp_path / "bad.tif"
    bad_path.write_bytes(b"not a real geotiff")
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps({"https://x/bad.tif": _topo_entry(bad_path)}))

    report = check_output_quality.topo_quads_verdict(manifest_path, sample_size=1)

    assert report["verdict"] is Verdict.PROBLEM
    assert any("readability re-check" in p for p in report["problems"])


def test_topo_quads_verdict_does_not_double_report_a_missing_file_as_also_unreadable(tmp_path):
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps({"https://x/gone.tif": _topo_entry(tmp_path / "gone.tif")}))

    report = check_output_quality.topo_quads_verdict(manifest_path, sample_size=1)

    assert len(report["problems"]) == 1


def test_resolve_topo_local_path_returns_an_absolute_path_unchanged():
    absolute = check_output_quality.ROOT / "data" / "raw" / "topo_quads" / "CT" / "x.tif"

    assert check_output_quality._resolve_topo_local_path(str(absolute)) == absolute


def test_resolve_topo_local_path_joins_a_relative_path_with_root():
    """fetch_topo_quads.py stores local_path relative to ROOT when possible
    (see fetch_one_quad()'s docstring) - this must reconstruct the same
    absolute path a script running from pipeline/ would resolve."""
    result = check_output_quality._resolve_topo_local_path("data/raw/topo_quads/CT/x.tif")

    assert result == check_output_quality.ROOT / "data" / "raw" / "topo_quads" / "CT" / "x.tif"


def test_quad_is_readable_true_for_a_valid_geotiff(tmp_path):
    path = tmp_path / "good.tif"
    _write_tiny_geotiff(path)

    assert check_output_quality._quad_is_readable(path) is True


def test_quad_is_readable_false_for_unreadable_bytes(tmp_path):
    path = tmp_path / "bad.tif"
    path.write_bytes(b"garbage, not a geotiff")

    assert check_output_quality._quad_is_readable(path) is False


def test_quad_is_readable_false_for_a_file_that_does_not_exist(tmp_path):
    assert check_output_quality._quad_is_readable(tmp_path / "does_not_exist.tif") is False


def _quad_manifest_urls(counts: dict) -> dict:
    """A synthetic manifest keyed the same way the real one is - full
    S3-shaped URLs with a state path segment - mirroring
    test_check_freshness.py's own _quad_manifest() fixture builder."""
    manifest = {}
    for state, count in counts.items():
        for i in range(count):
            url = f"https://prd-tnm.s3.amazonaws.com/StagedProducts/Maps/USTopo/GeoTIFF/{state}/{state}_quad_{i:03}.tif"
            manifest[url] = _topo_entry(f"data/raw/topo_quads/{state}/{state}_quad_{i:03}.tif")
    return manifest


def test_topo_readability_sample_never_exceeds_what_the_manifest_actually_has():
    manifest = _quad_manifest_urls({"CT": 3})

    sample = check_output_quality.topo_readability_sample(manifest, size=25)

    assert set(sample) == set(manifest)


def test_topo_readability_sample_of_an_empty_manifest_is_empty():
    assert check_output_quality.topo_readability_sample({}, size=25) == []


def test_topo_readability_sample_spreads_across_the_full_range_not_a_flat_prefix():
    """A flat sorted(manifest)[:size] prefix would be permanently limited to
    whichever state sorts alphabetically first - the exact bug
    check_freshness.py's topo_sample() was written to fix for the remote
    HTTP-sampling case. A stride across the whole sorted list reaches every
    state here too."""
    manifest = _quad_manifest_urls({"CT": 40, "GA": 40, "VA": 40, "WV": 40})

    sample = check_output_quality.topo_readability_sample(manifest, size=20)

    states = {url.rsplit("/", 2)[-2] for url in sample}
    assert states == {"CT", "GA", "VA", "WV"}


def test_topo_readability_sample_size_respects_a_monkeypatched_module_constant(monkeypatch):
    """Regression guard for the default-bound-at-import-time gotcha (see
    check_freshness.py's own equivalent test for topo_sample()): `size`
    must resolve TOPO_READABILITY_SAMPLE_SIZE inside the function body via a
    None sentinel, not as a plain `=TOPO_READABILITY_SAMPLE_SIZE` signature
    default, or this monkeypatch would silently stop taking effect."""
    manifest = _quad_manifest_urls({"CT": 10})
    monkeypatch.setattr(check_output_quality, "TOPO_READABILITY_SAMPLE_SIZE", 3)

    sample = check_output_quality.topo_readability_sample(manifest)

    assert len(sample) == 3


def test_topo_readability_sample_is_deterministic():
    """Same manifest, same sample every time - unlike check_freshness.py's
    day-seeded remote sample, this local readability spot-check has no
    upstream-timing reason to vary run to run, so it should not be flaky to
    assert on."""
    manifest = _quad_manifest_urls({"CT": 40, "GA": 20, "VA": 30})

    first = check_output_quality.topo_readability_sample(manifest, size=25)
    second = check_output_quality.topo_readability_sample(manifest, size=25)

    assert first == second


# --- Check 4: baseline_verdict / flag_drops / load_baseline / save_baseline --


def test_load_baseline_returns_none_when_the_file_does_not_exist(tmp_path):
    assert check_output_quality.load_baseline(tmp_path / "absent.json") is None


def test_save_baseline_then_load_baseline_roundtrips(tmp_path):
    path = tmp_path / "quality_baseline.json"
    check_output_quality.save_baseline({"trails": 4224, "elevation": 139219}, path)

    assert check_output_quality.load_baseline(path) == {"trails": 4224, "elevation": 139219}


def test_save_baseline_keeps_counts_a_partial_run_did_not_rebuild(tmp_path):
    """A run that skipped elevation must not erase elevation's last
    known-good figure. save_baseline() merges rather than replaces, so a
    partial publish records what it built without forgetting what it
    didn't."""
    path = tmp_path / "quality_baseline.json"
    check_output_quality.save_baseline({"trails": 4224, "elevation": 139219}, path)

    # What a `--optional elevation` run produces: no elevation counts at all.
    check_output_quality.save_baseline({"trails": 4224}, path)

    assert check_output_quality.load_baseline(path) == {"trails": 4224, "elevation": 139219}


def test_save_baseline_still_takes_the_new_figure_for_what_a_run_did_rebuild(tmp_path):
    """Merging must not turn the baseline into a high-water mark. A count
    this run actually measured replaces the old one, in both directions -
    otherwise an accepted, explained drop would keep re-flagging forever."""
    path = tmp_path / "quality_baseline.json"
    check_output_quality.save_baseline({"trails": 4224, "elevation": 139219}, path)

    check_output_quality.save_baseline({"trails": 3000, "elevation": 200000}, path)

    assert check_output_quality.load_baseline(path) == {"trails": 3000, "elevation": 200000}


def test_a_partial_run_does_not_blind_the_next_full_runs_drop_detection(tmp_path):
    """The bug --optional introduced, end to end at the baseline layer.

    Before --optional, a missing manifest was a PROBLEM, so a partial run
    exited non-zero and never recorded a baseline at all - the protection
    was accidental. Making partial runs pass removed it: the run then wrote
    a baseline with no elevation entry, and flag_drops() only compares names
    present in both sides, so the next full run had nothing to compare
    against and waved a total collapse straight through."""
    path = tmp_path / "quality_baseline.json"
    check_output_quality.save_baseline({"trails": 4224, "elevation": 139219}, path)

    # A publish-vector-data run with include_elevation off - the default path.
    check_output_quality.save_baseline({"trails": 4224}, path)

    # The next full run, with elevation collapsed to almost nothing.
    drops = check_output_quality.flag_drops({"trails": 4224, "elevation": 12}, check_output_quality.load_baseline(path))

    assert any("elevation" in d for d in drops), "a partial run must not blind the next full one"


def test_flag_drops_is_empty_when_nothing_dropped():
    assert check_output_quality.flag_drops({"trails": 100}, {"trails": 100}) == []


def test_flag_drops_is_empty_when_a_count_increased():
    assert check_output_quality.flag_drops({"trails": 150}, {"trails": 100}) == []


def test_flag_drops_flags_a_drop_over_the_threshold():
    problems = check_output_quality.flag_drops({"trails": 85}, {"trails": 100})

    assert len(problems) == 1
    assert "trails" in problems[0]
    assert "15.0%" in problems[0]


def test_flag_drops_does_not_flag_a_drop_under_the_threshold():
    assert check_output_quality.flag_drops({"trails": 91}, {"trails": 100}) == []


def test_flag_drops_does_not_flag_a_drop_of_exactly_the_threshold():
    """ "More than 10%" (the task's own framing) is exclusive - exactly 10%
    should not fire, only strictly more."""
    assert check_output_quality.flag_drops({"trails": 90}, {"trails": 100}, threshold=0.10) == []


def test_flag_drops_flags_a_drop_of_just_over_the_threshold():
    assert check_output_quality.flag_drops({"trails": 89}, {"trails": 100}, threshold=0.10) != []


def test_flag_drops_respects_a_monkeypatched_module_constant_threshold(monkeypatch):
    """Same default-bound-at-import-time gotcha guard as
    topo_readability_sample()'s test above, applied to `threshold` here."""
    monkeypatch.setattr(check_output_quality, "DROP_THRESHOLD", 0.5)

    assert check_output_quality.flag_drops({"trails": 60}, {"trails": 100}) == []


def test_flag_drops_suppresses_a_flagged_drop_when_a_matching_upstream_source_changed():
    problems = check_output_quality.flag_drops({"trails": 85}, {"trails": 100}, changed_sources={"atc"})

    assert problems == []


def test_flag_drops_still_flags_when_the_changed_source_does_not_match():
    """trails depends on "atc" (centerline/side_trails) - a reported
    "opentrail" change cannot explain a trails drop."""
    problems = check_output_quality.flag_drops({"trails": 85}, {"trails": 100}, changed_sources={"opentrail"})

    assert len(problems) == 1


def test_flag_drops_ignores_a_name_absent_from_current():
    """A manifest that is entirely missing is already its own PROBLEM from
    trails_verdict()/poi_verdict()/elevation_verdict() directly - reporting
    it again here as a "100% drop" would just restate the same fact."""
    assert check_output_quality.flag_drops({}, {"trails": 100}) == []


def test_flag_drops_ignores_a_zero_baseline():
    assert check_output_quality.flag_drops({"poi:crossing": 0}, {"poi:crossing": 0}) == []


def test_baseline_verdict_is_skipped_when_no_baseline_exists_yet(tmp_path):
    report = check_output_quality.baseline_verdict({"trails": 100}, tmp_path / "absent.json")

    assert report["verdict"] is Verdict.SKIPPED


def test_baseline_verdict_ok_when_there_are_no_drops(tmp_path):
    path = tmp_path / "quality_baseline.json"
    check_output_quality.save_baseline({"trails": 100}, path)

    report = check_output_quality.baseline_verdict({"trails": 100}, path)

    assert report["verdict"] is Verdict.OK


def test_baseline_verdict_is_problem_when_a_drop_is_unexplained(tmp_path):
    path = tmp_path / "quality_baseline.json"
    check_output_quality.save_baseline({"trails": 100}, path)

    report = check_output_quality.baseline_verdict({"trails": 50}, path)

    assert report["verdict"] is Verdict.PROBLEM
    assert len(report["problems"]) == 1


# --- Orchestration: _safe_verdict / check_all / main --------------------------


def test_safe_verdict_converts_an_exception_into_a_problem_report_instead_of_raising():
    def boom():
        raise ValueError("synthetic failure")

    report = check_output_quality._safe_verdict("widget", boom)

    assert report["verdict"] is Verdict.PROBLEM
    assert report["check"] == "widget"
    assert "synthetic failure" in report["problems"][0]
    assert report["counts"] == {}


def test_safe_verdict_passes_through_a_normal_result_unchanged():
    report = check_output_quality._safe_verdict("widget", lambda: {"check": "widget", "verdict": Verdict.OK})

    assert report == {"check": "widget", "verdict": Verdict.OK}


def test_check_all_returns_one_report_per_check(tmp_path, monkeypatch):
    for attr in ("TRAILS_MANIFEST", "POI_MANIFEST", "ELEVATION_MANIFEST", "SPURS_MANIFEST", "TOPO_QUADS_MANIFEST"):
        monkeypatch.setattr(check_output_quality, attr, tmp_path / "absent.json")
    monkeypatch.setattr(check_output_quality, "CENTERLINE_PATH", tmp_path / "absent.geojson")
    monkeypatch.setattr(check_output_quality, "BASELINE_PATH", tmp_path / "absent_baseline.json")

    reports = check_output_quality.check_all()

    assert {r["check"] for r in reports} == {
        "trails",
        "poi",
        "elevation",
        "spurs",
        "manifests",
        "corridor",
        "topo_quads",
        "water_reach",
        "baseline",
        "fetches",
    }


def test_check_all_topo_quads_and_baseline_are_skipped_not_problem_when_nothing_has_run_yet(tmp_path, monkeypatch):
    for attr in ("TRAILS_MANIFEST", "POI_MANIFEST", "ELEVATION_MANIFEST", "SPURS_MANIFEST"):
        monkeypatch.setattr(check_output_quality, attr, tmp_path / "absent.json")
    monkeypatch.setattr(check_output_quality, "CENTERLINE_PATH", tmp_path / "absent.geojson")
    monkeypatch.setattr(check_output_quality, "TOPO_QUADS_MANIFEST", tmp_path / "absent_topo.json")
    monkeypatch.setattr(check_output_quality, "BASELINE_PATH", tmp_path / "absent_baseline.json")

    reports = check_output_quality.check_all()

    by_check = {r["check"]: r["verdict"] for r in reports}
    assert by_check["topo_quads"] is Verdict.SKIPPED
    assert by_check["baseline"] is Verdict.SKIPPED
    assert by_check["trails"] is Verdict.PROBLEM


# --- check 5: fetch receipts (#542) ------------------------------------------


def _write_receipts(root, fetchers, *, now=None):
    """Give `root` a real receipt per fetcher, each standing behind a real
    file. Built through fetch_receipts.record() rather than by writing the
    JSON by hand, so these tests exercise the same writer the fetchers use -
    a hand-rolled fixture would keep passing after the format moved."""
    written = {}
    for name in fetchers:
        output = root / "data" / "raw" / f"{name}_output.json"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(f'{{"from": "{name}"}}')
        written[name] = output
        fetch_receipts.record(name, [output], root=root, now=now)
    return written


def test_fetches_verdict_is_ok_when_the_required_pair_left_receipts(tmp_path):
    _write_receipts(tmp_path, ["fetch_all", "fetch_opentrail"])

    report = check_output_quality.fetches_verdict(root=tmp_path)

    assert report["verdict"] is Verdict.OK
    assert report["problems"] == []


def test_fetches_verdict_fails_when_a_required_fetcher_never_ran(tmp_path):
    """The failure this check exists for. Every export can still be perfect -
    they will have been built from whatever the last run left on disk."""
    _write_receipts(tmp_path, ["fetch_all"])

    report = check_output_quality.fetches_verdict(root=tmp_path)

    assert report["verdict"] is Verdict.PROBLEM
    assert len(report["problems"]) == 1
    assert "fetch_opentrail" in report["problems"][0]


def test_fetches_verdict_fails_when_an_output_changed_since_it_was_fetched(tmp_path):
    outputs = _write_receipts(tmp_path, ["fetch_all", "fetch_opentrail"])
    outputs["fetch_all"].write_text('{"truncated": true}')

    report = check_output_quality.fetches_verdict(root=tmp_path)

    assert report["verdict"] is Verdict.PROBLEM
    assert "changed since it was fetched" in report["problems"][0]


def test_fetches_verdict_does_not_ask_for_elevation_unless_the_run_did(tmp_path):
    """Elevation is a workflow_dispatch input, so a run without it is a
    deliberate subset rather than a broken run - the same reasoning
    --optional already applies to the export side."""
    _write_receipts(tmp_path, ["fetch_all", "fetch_opentrail"])

    assert check_output_quality.fetches_verdict(root=tmp_path)["verdict"] is Verdict.OK
    assert check_output_quality.fetches_verdict(fetched={"fetch_elevation"}, root=tmp_path)["verdict"] is Verdict.PROBLEM


def test_fetches_verdict_asks_for_atc_photos_when_the_run_fetched_photos(tmp_path):
    """ATC photos have no continue-on-error: the workflow says an outage
    there means the release "has bigger problems than missing photos"."""
    _write_receipts(tmp_path, ["fetch_all", "fetch_opentrail"])

    report = check_output_quality.fetches_verdict(fetched={"fetch_atc_photos"}, root=tmp_path)

    assert report["verdict"] is Verdict.PROBLEM
    assert "fetch_atc_photos" in report["problems"][0]


def test_a_missing_commons_receipt_is_reported_but_never_fails(tmp_path):
    """fetch_poi_images.py carries continue-on-error because Commons is a
    third party this project has no relationship with. A gate that failed on
    its absence would contradict the step that produces it - but silence is
    how a release ships with no photos and nobody notices, so it is still
    said out loud."""
    _write_receipts(tmp_path, ["fetch_all", "fetch_opentrail"])

    report = check_output_quality.fetches_verdict(fetched={"fetch_poi_images"}, root=tmp_path)

    assert report["verdict"] is Verdict.OK
    assert "fetch_poi_images never" in report["detail"]


def test_a_stale_receipt_passes_and_says_how_stale(tmp_path):
    """#542 is explicit: "a release built while poi_images.json is a week old
    is a legitimate release". Staleness is something packaging reports so a
    reader can judge it, not something it decides for them."""
    _write_receipts(
        tmp_path,
        ["fetch_all", "fetch_opentrail"],
        now=datetime.now(timezone.utc) - timedelta(days=30),
    )

    report = check_output_quality.fetches_verdict(root=tmp_path)

    assert report["verdict"] is Verdict.OK
    assert "fetch_all 30.0d" in report["detail"]


def test_a_corrupt_receipt_fails_rather_than_reading_as_absent(tmp_path):
    _write_receipts(tmp_path, ["fetch_all", "fetch_opentrail"])
    fetch_receipts.receipt_path("fetch_all", tmp_path).write_text("{ half a file")

    report = check_output_quality.fetches_verdict(root=tmp_path)

    assert report["verdict"] is Verdict.PROBLEM
    assert "not readable JSON" in report["problems"][0]


def test_a_corrupt_receipt_fails_even_for_the_advisory_fetcher(tmp_path):
    """Commons is allowed not to have run. It is not allowed to leave a torn
    file where a completion record belongs - that is something going wrong
    locally, not a third party being down."""
    _write_receipts(tmp_path, ["fetch_all", "fetch_opentrail"])
    fetch_receipts.receipts_dir(tmp_path).mkdir(parents=True, exist_ok=True)
    fetch_receipts.receipt_path("fetch_poi_images", tmp_path).write_text("{ torn")

    report = check_output_quality.fetches_verdict(root=tmp_path)

    assert report["verdict"] is Verdict.PROBLEM


def test_the_fetches_check_is_never_excused_by_optional(tmp_path, monkeypatch):
    """--optional's excuse is keyed on "the manifest was absent, so this was
    never built". The fetches check has the opposite polarity - an absent
    receipt IS the finding - so it must not be reachable through the same
    door, whatever a caller passes."""
    monkeypatch.setattr(check_output_quality, "RECEIPTS_ROOT", tmp_path)
    for attr in ("TRAILS_MANIFEST", "POI_MANIFEST", "ELEVATION_MANIFEST", "SPURS_MANIFEST"):
        monkeypatch.setattr(check_output_quality, attr, tmp_path / "absent.json")
    monkeypatch.setattr(check_output_quality, "CENTERLINE_PATH", tmp_path / "absent.geojson")
    monkeypatch.setattr(check_output_quality, "TOPO_QUADS_MANIFEST", tmp_path / "absent_topo.json")
    monkeypatch.setattr(check_output_quality, "BASELINE_PATH", tmp_path / "absent_baseline.json")

    reports = check_output_quality.check_all(optional={"trails", "poi", "elevation", "fetches"})

    by_check = {r["check"]: r["verdict"] for r in reports}
    assert by_check["fetches"] is Verdict.PROBLEM


def test_main_fails_when_a_required_fetch_left_no_receipt(passing_pipeline, tmp_path):
    """End to end through the process exit code: everything else is green and
    the release still stops."""
    assert check_output_quality.main() == 0

    fetch_receipts.receipt_path("fetch_opentrail", tmp_path).unlink()

    assert check_output_quality.main() != 0


def test_main_accepts_the_fetched_flag_for_a_conditional_fetcher(passing_pipeline, tmp_path):
    assert check_output_quality.main(["--fetched", "fetch_elevation"]) != 0

    _write_receipts(tmp_path, ["fetch_elevation"])

    assert check_output_quality.main(["--fetched", "fetch_elevation"]) == 0


def test_the_fetched_flag_rejects_a_fetcher_that_is_always_required():
    """fetch_all and fetch_opentrail are not optional and never need naming,
    so accepting them would imply a run could choose not to need them."""
    with pytest.raises(SystemExit):
        check_output_quality.parse_args(["--fetched", "fetch_all"])


@pytest.fixture
def passing_pipeline(tmp_path, monkeypatch):
    """A complete, self-consistent, passing set of manifests plus a real
    (tiny, synthetic) centerline - enough for trails_verdict/poi_verdict/
    elevation_verdict/spurs_verdict/corridor_verdict to all report OK.
    topo_quads and baseline are left absent on purpose (SKIPPED, which never
    gates exit_code) so this fixture stays focused on the checks that always
    run given this module's documented position in the pipeline."""
    trails_manifest = tmp_path / "trails_manifest.json"
    trails_manifest.write_text(
        json.dumps(
            {
                "geojson": _artifact_entry(tmp_path / "trails.geojson", "geojson bytes", 10),
                "fgb": _artifact_entry(tmp_path / "trails.fgb", "fgb bytes", 10),
            }
        )
    )

    poi_manifest = tmp_path / "poi_manifest.json"
    poi_manifest.write_text(json.dumps(_poi_manifest(tmp_path, {"crossing": 0})))

    elevation_manifest = tmp_path / "elevation_manifest.json"
    elevation_entry = _artifact_entry(tmp_path / "elevation_profile.json", "elevation bytes", 0)
    elevation_manifest.write_text(
        json.dumps(
            {
                "path": elevation_entry["path"],
                "sha256": elevation_entry["sha256"],
                "point_count": 139219,
                "null_elevation_count": 0,
                "null_elevation_pct": 0.0,
            }
        )
    )

    spurs_manifest = tmp_path / "spurs_manifest.json"
    spurs_entry = _artifact_entry(tmp_path / "spurs.json", "spurs bytes", 0)
    spurs_manifest.write_text(
        json.dumps(
            {
                "path": spurs_entry["path"],
                "sha256": spurs_entry["sha256"],
                "spur_count": 62,
                "resolved_count": 41,
            }
        )
    )

    centerline_path = tmp_path / "centerline.geojson"
    write_centerline(centerline_path)

    # The two always-required fetch receipts (#542). Added here rather than
    # excused in the check, because "a complete, passing set" genuinely now
    # includes them: a run whose exports are perfect but whose inputs were
    # never fetched this time is the case fetches_verdict() exists to catch,
    # so a fixture that passed without them would be asserting the opposite
    # of what the check is for.
    _write_receipts(tmp_path, ["fetch_all", "fetch_opentrail"])

    # The club sections manifest joined the passing set with #659's
    # manifests check; stretch manifests stay absent on purpose (noted,
    # never failed - most vector runs rightly have none).
    club_manifest = tmp_path / "club_sections_manifest.json"
    club_entry = _artifact_entry(tmp_path / "club_sections.json", "club bytes", 0)
    club_manifest.write_text(json.dumps({"path": club_entry["path"], "sha256": club_entry["sha256"]}))

    monkeypatch.setattr(check_output_quality, "RECEIPTS_ROOT", tmp_path)
    monkeypatch.setattr(check_output_quality, "TRAILS_MANIFEST", trails_manifest)
    monkeypatch.setattr(check_output_quality, "POI_MANIFEST", poi_manifest)
    monkeypatch.setattr(check_output_quality, "ELEVATION_MANIFEST", elevation_manifest)
    monkeypatch.setattr(check_output_quality, "SPURS_MANIFEST", spurs_manifest)
    monkeypatch.setattr(check_output_quality, "CLUB_SECTIONS_MANIFEST", club_manifest)
    monkeypatch.setattr(check_output_quality, "PROCESSED_DIR", tmp_path)
    monkeypatch.setattr(check_output_quality, "CENTERLINE_PATH", centerline_path)
    monkeypatch.setattr(check_output_quality, "TOPO_QUADS_MANIFEST", tmp_path / "absent_topo_manifest.json")
    monkeypatch.setattr(check_output_quality, "BASELINE_PATH", tmp_path / "quality_baseline.json")


def test_main_returns_zero_when_everything_passes(passing_pipeline):
    assert check_output_quality.main() == 0


def test_main_writes_a_new_baseline_only_when_everything_passes(passing_pipeline):
    check_output_quality.main()

    baseline = json.loads(check_output_quality.BASELINE_PATH.read_text())
    assert baseline["counts"]["trails"] == 10
    assert baseline["counts"]["elevation"] == 139219
    assert baseline["counts"]["poi:crossing"] == 0


def test_main_does_not_write_a_baseline_when_a_check_fails(passing_pipeline, tmp_path):
    (tmp_path / "trails.geojson").write_text("tampered after the manifest recorded its hash")

    exit_code = check_output_quality.main()

    assert exit_code != 0
    assert not check_output_quality.BASELINE_PATH.exists()


def test_main_flags_a_baseline_drop_on_a_second_run(passing_pipeline, tmp_path):
    """End-to-end: a first passing run records a baseline; a second run
    whose shelter count collapsed 5 -> 1 (still >= poi_verdict's own
    per-type minimum of 1, so poi_verdict ALONE reports OK on this second
    run) must still fail overall - only the baseline comparison can catch a
    real 80% decline that stays technically non-empty."""
    assert check_output_quality.main() == 0

    collapsed_poi_manifest = _poi_manifest(tmp_path, {"crossing": 0, "shelter": 1})
    check_output_quality.POI_MANIFEST.write_text(json.dumps(collapsed_poi_manifest))

    second_poi_report = check_output_quality.poi_verdict(check_output_quality.POI_MANIFEST)
    assert second_poi_report["verdict"] is Verdict.OK  # confirms this is really testing check #4, not check #1

    exit_code = check_output_quality.main()

    assert exit_code != 0


def test_main_fails_when_an_expected_artifact_was_never_built(passing_pipeline):
    """The default stays strict: a missing manifest is a problem unless the
    caller says otherwise. This is what --optional has to not break."""
    check_output_quality.ELEVATION_MANIFEST.unlink()

    assert check_output_quality.main() != 0


def test_main_skips_an_artifact_the_run_was_never_meant_to_build(passing_pipeline):
    """A CI job that publishes only trails and POIs legitimately has no
    elevation manifest. publish.py already supports that partial publish, so
    a gate in front of it that insists on the full set contradicts the thing
    it is gating."""
    check_output_quality.ELEVATION_MANIFEST.unlink()

    assert check_output_quality.main(["--optional", "elevation"]) == 0


def test_optional_does_not_excuse_an_artifact_that_exists_and_is_wrong(passing_pipeline, tmp_path):
    """The distinction the flag rests on: "I did not build it" is excusable,
    "I built it and it is broken" is not. Tampering with the artifact after
    the manifest recorded its hash must still fail, --optional or not."""
    (tmp_path / "elevation_profile.json").write_text("tampered after hashing")

    assert check_output_quality.main(["--optional", "elevation"]) != 0


# --- as_optional -------------------------------------------------------------
#
# Tested directly as well as through main() below. The whole --optional feature
# rests on this one function drawing the line between "I did not build it" and
# "I built it and it is wrong", and going through main() means a full on-disk
# pipeline fixture per case - which makes the cheap, exhaustive cases expensive
# enough not to write. These are the exhaustive ones.


def test_as_optional_excuses_a_manifest_that_was_never_built():
    report = {
        "check": "elevation",
        "verdict": Verdict.PROBLEM,
        "detail": "gone",
        "problems": ["gone"],
        "counts": {},
        "reason": check_output_quality.MANIFEST_MISSING,
    }

    assert check_output_quality.as_optional(report)["verdict"] is Verdict.SKIPPED


def test_as_optional_clears_the_problems_it_excused():
    """A SKIPPED check carrying problems would still print them, reading as a
    failure that somehow passed."""
    report = {
        "check": "elevation",
        "verdict": Verdict.PROBLEM,
        "detail": "gone",
        "problems": ["gone"],
        "counts": {},
        "reason": check_output_quality.MANIFEST_MISSING,
    }

    assert check_output_quality.as_optional(report)["problems"] == []


def test_as_optional_refuses_a_problem_with_no_reason_recorded():
    """_safe_verdict()'s catch-all builds a PROBLEM with no `reason` - a check
    that CRASHED. Excusing that would turn every unexpected exception in an
    optional check into a silent pass."""
    report = {"check": "elevation", "verdict": Verdict.PROBLEM, "detail": "boom", "problems": ["boom"], "counts": {}}

    assert check_output_quality.as_optional(report)["verdict"] is Verdict.PROBLEM


def test_as_optional_refuses_a_problem_reported_for_some_other_reason():
    report = {
        "check": "elevation",
        "verdict": Verdict.PROBLEM,
        "detail": "sha256 mismatch",
        "problems": ["sha256 mismatch"],
        "counts": {},
        "reason": "something-else",
    }

    assert check_output_quality.as_optional(report)["verdict"] is Verdict.PROBLEM


def test_as_optional_leaves_a_passing_check_exactly_as_it_found_it():
    report = {"check": "elevation", "verdict": Verdict.OK, "detail": "fine", "problems": [], "counts": {"elevation": 10}}

    assert check_output_quality.as_optional(report) == report


def test_as_optional_leaves_an_already_skipped_check_alone():
    report = {"check": "baseline", "verdict": Verdict.SKIPPED, "detail": "no baseline yet", "problems": [], "counts": {}}

    assert check_output_quality.as_optional(report) == report


def test_every_missing_manifest_verdict_records_the_reason(tmp_path):
    """The three verdict functions set `reason` structurally rather than
    as_optional() sniffing it out of the problem text - and if one of them
    ever stops, --optional silently stops excusing that artifact."""
    for verdict_fn in (
        check_output_quality.trails_verdict,
        check_output_quality.poi_verdict,
        check_output_quality.elevation_verdict,
    ):
        report = verdict_fn(tmp_path / "absent.json")

        assert report["verdict"] is Verdict.PROBLEM
        assert report["reason"] == check_output_quality.MANIFEST_MISSING, verdict_fn.__name__
        assert check_output_quality.as_optional(report)["verdict"] is Verdict.SKIPPED


def test_optional_does_not_excuse_a_manifest_whose_artifact_vanished(passing_pipeline, tmp_path):
    """The near-miss the first version of --optional actually got wrong.

    It decided what to excuse by looking for "missing" in the problem text,
    and artifact_problems() says "file missing on disk" for a manifest that
    IS present whose artifact has gone - the opposite situation. A run that
    built elevation and then lost the file was being waved through as
    though it had never built it.

    The tampered-file test above did not catch it, because that path
    reports "sha256 mismatch" instead. Hence the structural `reason` field
    rather than a smarter substring."""
    (tmp_path / "elevation_profile.json").unlink()

    assert check_output_quality.main(["--optional", "elevation"]) != 0


def test_main_accepts_a_changed_source_that_explains_the_drop(passing_pipeline, tmp_path):
    """The suppression path, reached the way an operator actually reaches it.

    flag_drops() has always known how to suppress a drop that an upstream
    change explains, but main() took no arguments - so nothing outside the
    tests could supply one, and every legitimate upstream-caused drop was
    reported as unexplained. Same collapse as the test above, with the
    explanation supplied on the command line."""
    assert check_output_quality.main() == 0

    collapsed_poi_manifest = _poi_manifest(tmp_path, {"crossing": 0, "shelter": 1})
    check_output_quality.POI_MANIFEST.write_text(json.dumps(collapsed_poi_manifest))

    # 'atc' is what COUNT_UPSTREAM_SOURCES says feeds poi:shelter.
    assert check_output_quality.main(["--changed-source", "atc"]) == 0


def test_main_still_flags_a_drop_an_unrelated_changed_source_cannot_explain(passing_pipeline, tmp_path):
    """Suppression is scoped to sources that actually feed the count that
    dropped - naming an unrelated one must not wave the drop through."""
    assert check_output_quality.main() == 0

    collapsed_poi_manifest = _poi_manifest(tmp_path, {"crossing": 0, "shelter": 1})
    check_output_quality.POI_MANIFEST.write_text(json.dumps(collapsed_poi_manifest))

    # poi:shelter is fed by 'atc' alone, so an elevation refresh explains nothing.
    assert check_output_quality.main(["--changed-source", "elevation"]) != 0
