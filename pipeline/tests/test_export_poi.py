"""Tests for export_poi.py - the unified-POI export step (ROADMAP.md's
"Unified POI schema" line, TECHNICAL_ARCHITECTURE.md's Export step). Small
synthetic fixtures throughout (tiny GeoJSON built in test code), never the
real ATC/opentrail.org data or the full corridor dataset - see TESTING.md.
"""

import hashlib
import json

import duckdb
import pytest

import export_poi
from lib.poi_schema import CONFIDENCE_HIGH, CONFIDENCE_LOW, POI_TYPES

# A small line near (-74, 41), same neighborhood other synthetic fixtures in
# this suite use (see test_spike_corridor.py) - far from any real data, so
# it can't collide with anything.
CENTERLINE_COORDS = [(-74.0, 41.0), (-73.9, 41.1)]


def _write_centerline(path, coords=CENTERLINE_COORDS):
    fc = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {},
                "geometry": {"type": "LineString", "coordinates": [[lon, lat] for lon, lat in coords]},
            }
        ],
    }
    path.write_text(json.dumps(fc))


def _point_feature(feature_id, lon, lat, properties):
    return {
        "type": "Feature",
        "id": feature_id,
        "geometry": {"type": "Point", "coordinates": [lon, lat]},
        "properties": properties,
    }


def _write_fc(path, features):
    path.write_text(json.dumps({"type": "FeatureCollection", "features": features}))


def _write_fixture_sources(raw_dir):
    """Tiny synthetic stand-ins for the four real raw sources, all placed
    near CENTERLINE_COORDS so they land inside a 30-mile corridor built from
    it. Field names match the real ones found by inspecting the actual raw
    ATC/opentrail.org files (GlobalID/Name for ATC, dbid/title/icon for
    opentrail.org)."""
    _write_centerline(raw_dir / "centerline.geojson")

    _write_fc(
        raw_dir / "shelters.geojson",
        [_point_feature(1, -73.95, 41.05, {"GlobalID": "shelter-glob-1", "OBJECTID": 1, "Name": "Test Shelter"})],
    )
    _write_fc(
        raw_dir / "campsites.geojson",
        [_point_feature(1, -73.94, 41.04, {"GlobalID": "campsite-glob-1", "OBJECTID": 1, "Name": "Test Campsite"})],
    )
    _write_fc(
        raw_dir / "communities.geojson",
        [_point_feature(1, -73.93, 41.03, {"GlobalID": "community-glob-1", "FID": 1, "NAME": "Test Town"})],
    )
    _write_fc(
        raw_dir / "opentrail_at.geojson",
        [
            _point_feature(0, -73.92, 41.02, {"title": "Test Spring", "icon": "w", "dbid": 100}),
            _point_feature(1, -73.91, 41.01, {"title": "Test Outfitter", "icon": "r", "dbid": 101}),
            # Real-data gotcha (verified against the actual opentrail_at.geojson
            # 2026-07-28): the `icon` value "s" is NOT shelter, despite there
            # being exactly 32 "s"-tagged features in the real file (a
            # suspiciously shelter-sized count). Every one actually inspected
            # is a spring/stream/seasonal-water point (e.g. "Piped spring",
            # "Seasonal Water Spigot") - opentrail.org's real AT dataset has
            # no shelter tag at all; ATC's own `shelters` source is the only
            # shelter source. See
            # test_export_poi_opentrail_seasonal_water_tag_is_not_treated_as_shelter.
            _point_feature(2, -73.90, 41.00, {"title": "Seasonal Spring", "icon": "s", "dbid": 102}),
            # Icons not folded into any poi_type - must not silently appear
            # as some default type.
            _point_feature(3, -73.89, 40.99, {"title": "Guidepost", "icon": "j", "dbid": 103}),
            _point_feature(4, -73.88, 40.98, {"title": "Trailhead", "icon": "o", "dbid": 104}),
        ],
    )


@pytest.fixture
def con():
    c = duckdb.connect()
    c.execute("INSTALL spatial; LOAD spatial;")
    return c


def test_export_poi_clips_features_outside_the_corridor(tmp_path, con):
    """A synthetic feature far from the trail should not appear in output -
    mirrors spike_corridor.py's own clip step, on tiny synthetic data rather
    than the full real 14GB dataset."""
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    _write_centerline(raw_dir / "centerline.geojson")

    export_poi.build_corridor(con, raw_dir / "centerline.geojson")

    unified = [
        {
            "id": "test:near",
            "poi_type": "shelter",
            "trail_id": "AT",
            "source": "test",
            "source_feature_id": "near",
            "name": "Near",
            "lat": 41.05,
            "lon": -73.95,
            "confidence": CONFIDENCE_HIGH,
        },
        {
            "id": "test:far",
            "poi_type": "shelter",
            "trail_id": "AT",
            "source": "test",
            "source_feature_id": "far",
            "name": "Far",
            "lat": 38.0,
            "lon": -70.0,
            "confidence": CONFIDENCE_HIGH,
        },
    ]

    clipped = export_poi.clip_to_corridor(con, unified)
    clipped_ids = {r["id"] for r in clipped}

    assert "test:near" in clipped_ids
    assert "test:far" not in clipped_ids


def test_export_poi_writes_a_sha256_hash_per_artifact_in_the_manifest(tmp_path, monkeypatch, con):
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    out_dir = tmp_path / "processed" / "poi"
    _write_fixture_sources(raw_dir)

    monkeypatch.setattr(export_poi, "RAW_DIR", raw_dir)
    monkeypatch.setattr(export_poi, "OUT_DIR", out_dir)

    manifest = export_poi.main()

    assert set(manifest.keys()) == set(POI_TYPES)
    shelter_entry = manifest["shelter"]
    for artifact_kind in ("geojson", "fgb"):
        entry = shelter_entry[artifact_kind]
        on_disk = (out_dir / f"shelter.{'geojson' if artifact_kind == 'geojson' else 'fgb'}").read_bytes()
        assert entry["sha256"] == hashlib.sha256(on_disk).hexdigest()
        assert len(entry["sha256"]) == 64

    manifest_path = out_dir / "manifest.json"
    assert manifest_path.exists()
    on_disk_manifest = json.loads(manifest_path.read_text())
    assert on_disk_manifest["shelter"]["geojson"]["sha256"] == shelter_entry["geojson"]["sha256"]


def test_export_poi_crossing_layer_is_present_but_empty_pending_nhd_ingestion(tmp_path, monkeypatch, con):
    """`crossing` is a real declared poi_type (ROADMAP.md's NHD-crossing item
    is still exploratory/undecided) - it must ship as a present-but-empty
    layer, not be silently omitted, and not contain invented data."""
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    out_dir = tmp_path / "processed" / "poi"
    _write_fixture_sources(raw_dir)

    monkeypatch.setattr(export_poi, "RAW_DIR", raw_dir)
    monkeypatch.setattr(export_poi, "OUT_DIR", out_dir)

    manifest = export_poi.main()

    assert "crossing" in manifest
    assert manifest["crossing"]["geojson"]["feature_count"] == 0
    assert manifest["crossing"]["fgb"]["feature_count"] == 0

    geojson_path = out_dir / "crossing.geojson"
    fgb_path = out_dir / "crossing.fgb"
    assert geojson_path.exists()
    assert fgb_path.exists()

    fc = json.loads(geojson_path.read_text())
    assert fc["features"] == []

    fgb_count = con.execute(f"SELECT COUNT(*) FROM ST_Read('{fgb_path.as_posix()}')").fetchone()[0]
    assert fgb_count == 0


def test_export_poi_a_non_crossing_type_returning_zero_features_fails_the_run(tmp_path, monkeypatch, con):
    """Unlike `crossing` (intentionally always empty pending NHD ingestion -
    see test_export_poi_crossing_layer_is_present_but_empty_pending_nhd_ingestion),
    every other poi_type is expected to be non-empty for real AT corridor
    data. A genuinely broken source - e.g. shelters.geojson silently coming
    back with zero features after an upstream schema change - must fail the
    run loudly instead of shipping a structurally-identical-to-crossing empty
    layer with no signal anything went wrong."""
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    out_dir = tmp_path / "processed" / "poi"
    _write_fixture_sources(raw_dir)
    _write_fc(raw_dir / "shelters.geojson", [])  # simulate shelter silently returning 0 features

    monkeypatch.setattr(export_poi, "RAW_DIR", raw_dir)
    monkeypatch.setattr(export_poi, "OUT_DIR", out_dir)

    with pytest.raises(SystemExit) as exc_info:
        export_poi.main()

    assert exc_info.value.code == 1
    # The manifest is the "this run succeeded" artifact - it must not be
    # written when the run is incomplete, matching fetch_all.py's pattern.
    assert not (out_dir / "manifest.json").exists()


def test_export_poi_opentrail_seasonal_water_tag_is_not_treated_as_shelter(tmp_path, monkeypatch, con):
    """Regression test for a real data gotcha (verified 2026-07-28 against
    the actual opentrail_at.geojson): the `icon` property's "s" value has
    exactly 32 occurrences in the real file - a suspiciously shelter-sized
    number that a naive tag-count match could mistake for "shelter" - but
    every "s"-tagged feature actually inspected is a spring/stream/seasonal-
    water point, not a shelter. Getting this wrong would mean showing a
    hiker a "shelter" that's actually just a spring - a real safety
    footgun, not a cosmetic bug."""
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    out_dir = tmp_path / "processed" / "poi"
    _write_fixture_sources(raw_dir)

    monkeypatch.setattr(export_poi, "RAW_DIR", raw_dir)
    monkeypatch.setattr(export_poi, "OUT_DIR", out_dir)

    export_poi.main()

    shelter_fc = json.loads((out_dir / "shelter.geojson").read_text())
    shelter_names = {f["properties"]["name"] for f in shelter_fc["features"]}
    assert "Seasonal Spring" not in shelter_names
    assert shelter_names == {"Test Shelter"}  # only the real ATC shelter source feeds this type

    water_fc = json.loads((out_dir / "water.geojson").read_text())
    water_names = {f["properties"]["name"] for f in water_fc["features"]}
    assert "Seasonal Spring" in water_names  # folded into water instead, per README's documented role


def test_export_poi_carries_fetched_photos_onto_their_features_and_only_theirs(tmp_path, monkeypatch, con):
    """When fetch_poi_images.py has left data/raw/poi_images.json, its found
    photos ride the matching exported features as photo_* properties -
    licence and author included, because per-photo attribution is the
    condition of shipping the photo at all (CONTRIBUTING.md's licence note).
    A recorded miss and an unmatched POI both export photo-less, identical
    to a run where the fetch never happened."""
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    out_dir = tmp_path / "processed" / "poi"
    _write_fixture_sources(raw_dir)
    (raw_dir / "poi_images.json").write_text(
        json.dumps(
            {
                "pois": {
                    "atc_shelters:shelter-glob-1": {
                        "status": "found",
                        "checked": "2026-08-07",
                        "photo": {
                            "title": "File:Test Shelter.jpg",
                            "distance_m": 42.5,
                            "url": "https://upload.wikimedia.org/test-shelter-640.jpg",
                            "page_url": "https://commons.wikimedia.org/wiki/File:Test_Shelter.jpg",
                            "author": "Jane Doe",
                            "license": "CC BY-SA 4.0",
                            "taken": "2025-06-18",
                        },
                    },
                    "opentrail_at:100": {"status": "none", "checked": "2026-08-07"},
                }
            }
        )
    )

    monkeypatch.setattr(export_poi, "RAW_DIR", raw_dir)
    monkeypatch.setattr(export_poi, "OUT_DIR", out_dir)

    export_poi.main()

    shelter_fc = json.loads((out_dir / "shelter.geojson").read_text())
    shelter_props = shelter_fc["features"][0]["properties"]
    assert shelter_props["photo_url"] == "https://upload.wikimedia.org/test-shelter-640.jpg"
    assert shelter_props["photo_page_url"] == "https://commons.wikimedia.org/wiki/File:Test_Shelter.jpg"
    assert shelter_props["photo_author"] == "Jane Doe"
    assert shelter_props["photo_license"] == "CC BY-SA 4.0"
    assert shelter_props["photo_taken"] == "2025-06-18"

    water_fc = json.loads((out_dir / "water.geojson").read_text())
    for feature in water_fc["features"]:
        # Recorded-miss and never-checked features alike: no photo value,
        # whether the driver writes the property as null or omits it.
        assert feature["properties"].get("photo_url") is None


def test_export_poi_exports_photo_less_when_no_images_file_exists(tmp_path, monkeypatch, con):
    """The images file being absent is a normal state (fetch_poi_images.py
    is optional and slow), not an error - the export must ship, and ship
    without inventing photo values."""
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    out_dir = tmp_path / "processed" / "poi"
    _write_fixture_sources(raw_dir)

    monkeypatch.setattr(export_poi, "RAW_DIR", raw_dir)
    monkeypatch.setattr(export_poi, "OUT_DIR", out_dir)

    manifest = export_poi.main()

    assert manifest["shelter"]["geojson"]["feature_count"] == 1
    shelter_fc = json.loads((out_dir / "shelter.geojson").read_text())
    assert shelter_fc["features"][0]["properties"].get("photo_url") is None


def test_export_poi_communities_and_opentrail_resupply_carry_different_confidence(tmp_path, monkeypatch, con):
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    out_dir = tmp_path / "processed" / "poi"
    _write_fixture_sources(raw_dir)

    monkeypatch.setattr(export_poi, "RAW_DIR", raw_dir)
    monkeypatch.setattr(export_poi, "OUT_DIR", out_dir)

    export_poi.main()

    resupply_fc = json.loads((out_dir / "resupply.geojson").read_text())
    by_name = {f["properties"]["name"]: f["properties"]["confidence"] for f in resupply_fc["features"]}

    assert by_name["Test Town"] == CONFIDENCE_LOW  # ATC Community proxy
    assert by_name["Test Outfitter"] == CONFIDENCE_HIGH  # real opentrail.org resupply tag
