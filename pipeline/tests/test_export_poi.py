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
from lib.photo_store import photo_digest
from lib.poi_schema import CONFIDENCE_HIGH, CONFIDENCE_LOW, POI_TYPES

# A small line near (-74, 41), same neighborhood other synthetic fixtures in
# this suite use (see test_spike_corridor.py) - far from any real data, so
# it can't collide with anything.
CENTERLINE_COORDS = [(-74.0, 41.0), (-73.9, 41.1)]

SHELTER_DIGEST = photo_digest(b"\xff\xd8 a test shelter photo")


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
        [
            _point_feature(
                1,
                -73.95,
                41.05,
                # The ATC inventory columns lib/poi_description.py composes
                # from ride alongside the identity ones.
                {
                    "GlobalID": "shelter-glob-1",
                    "OBJECTID": 1,
                    "Name": "Test Shelter",
                    "Stories": 2,
                    "Exterior_M": "5",
                    "Chimneys": 1,
                    "Year_Built": 1954,
                },
            )
        ],
    )
    _write_fc(
        raw_dir / "campsites.geojson",
        [
            _point_feature(
                1,
                -73.94,
                41.04,
                {"GlobalID": "campsite-glob-1", "OBJECTID": 1, "Name": "Test Campsite", "Type": "0", "Site_Num": 3},
            )
        ],
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


@pytest.fixture(autouse=True)
def no_real_capacity_file(tmp_path, monkeypatch):
    """Point CAPACITY_PATH away from the checked-in reference/ file for every
    test here, so a suite of synthetic fixtures cannot quietly start reading
    280 real ATC shelters (TESTING.md - never the real data). Tests that want
    capacities write their own file and patch this again."""
    monkeypatch.setattr(export_poi, "CAPACITY_PATH", tmp_path / "no-capacity-file.json")


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
                            # Where the bytes came from - provenance only. The
                            # feature must not carry this; #362 replaced the
                            # hotlink with our own copy.
                            "url": "https://upload.wikimedia.org/test-shelter-640.jpg",
                            "digest": SHELTER_DIGEST,
                            "page_url": "https://commons.wikimedia.org/wiki/File:Test_Shelter.jpg",
                            "author": "Jane Doe",
                            "license": "CC BY-SA 4.0",
                            "taken": "2025-06-18",
                        },
                    },
                    "opentrail_at:100": {"status": "none", "checked": "2026-08-07"},
                    # Recorded before the download step existed: no digest, so
                    # nothing names it in our bucket and it must not export.
                    "atc_campsites:campsite-glob-1": {
                        "status": "found",
                        "checked": "2026-08-07",
                        "photo": {"url": "https://upload.wikimedia.org/legacy.jpg", "taken": "2025-06-18"},
                    },
                }
            }
        )
    )

    monkeypatch.setattr(export_poi, "RAW_DIR", raw_dir)
    monkeypatch.setattr(export_poi, "OUT_DIR", out_dir)

    export_poi.main()

    shelter_fc = json.loads((out_dir / "shelter.geojson").read_text())
    shelter_props = shelter_fc["features"][0]["properties"]
    # A bucket key, not a URL: the host comes from the client's build-time
    # base, so published data survives moving bucket or putting a CDN in front.
    assert shelter_props["photo_key"] == f"photos/{SHELTER_DIGEST}.jpg"
    assert "upload.wikimedia.org" not in json.dumps(shelter_props)
    assert shelter_props["photo_page_url"] == "https://commons.wikimedia.org/wiki/File:Test_Shelter.jpg"
    assert shelter_props["photo_author"] == "Jane Doe"
    assert shelter_props["photo_license"] == "CC BY-SA 4.0"
    assert shelter_props["photo_taken"] == "2025-06-18"

    water_fc = json.loads((out_dir / "water.geojson").read_text())
    for feature in water_fc["features"]:
        # Recorded-miss and never-checked features alike: no photo value,
        # whether the driver writes the property as null or omits it.
        assert feature["properties"].get("photo_key") is None

    # The digest-less legacy record exports photo-less rather than falling
    # back to the Commons URL, which would reinstate the hotlink.
    campsite_fc = json.loads((out_dir / "campsite.geojson").read_text())
    campsite_props = campsite_fc["features"][0]["properties"]
    assert campsite_props.get("photo_key") is None
    assert "upload.wikimedia.org" not in json.dumps(campsite_props)


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
    assert shelter_fc["features"][0]["properties"].get("photo_key") is None


def _write_capacity_file(path, records):
    """A stand-in for reference/shelter_capacity.json, same shape
    build_shelter_capacity.py writes."""
    path.write_text(json.dumps({"shelters": records}))


def test_export_poi_carries_shelter_capacity_onto_the_shelter_feature(tmp_path, monkeypatch, con):
    """shelter_capacity.json's numbers reach the exported shelter features,
    keyed by the ATC GlobalID the unified id is built from - and reach
    nothing else. Capacity is a shelter fact; a campsite or a spring
    carrying one would be a column shift, not a feature."""
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    out_dir = tmp_path / "processed" / "poi"
    _write_fixture_sources(raw_dir)
    capacity_path = tmp_path / "shelter_capacity.json"
    _write_capacity_file(
        capacity_path,
        [
            {"atc_global_id": "shelter-glob-1", "atc_name": "Test Shelter", "capacity": 8},
            # A shelter that is not in this corridor: present in the file,
            # absent from the export, and no reason for either to complain.
            {"atc_global_id": "shelter-glob-absent", "atc_name": "Elsewhere Shelter", "capacity": 12},
        ],
    )

    monkeypatch.setattr(export_poi, "RAW_DIR", raw_dir)
    monkeypatch.setattr(export_poi, "OUT_DIR", out_dir)
    monkeypatch.setattr(export_poi, "CAPACITY_PATH", capacity_path)

    export_poi.main()

    shelter_fc = json.loads((out_dir / "shelter.geojson").read_text())
    assert shelter_fc["features"][0]["properties"]["capacity"] == 8

    campsite_fc = json.loads((out_dir / "campsite.geojson").read_text())
    assert campsite_fc["features"][0]["properties"].get("capacity") is None
    water_fc = json.loads((out_dir / "water.geojson").read_text())
    for feature in water_fc["features"]:
        assert feature["properties"].get("capacity") is None


def test_export_poi_publishes_no_capacity_where_the_reference_file_states_none(tmp_path, monkeypatch, con):
    """A shelter the source could not be read for exports NULL, not 0 and not
    a guess. build_shelter_capacity.py leaves 18 of ATC's 280 shelters this
    way on purpose - a pair listed under one number, a capacity written
    "xxx" - and every one of them must reach a hiker as a card that says
    nothing rather than a number nobody stands behind."""
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    out_dir = tmp_path / "processed" / "poi"
    _write_fixture_sources(raw_dir)
    capacity_path = tmp_path / "shelter_capacity.json"
    _write_capacity_file(
        capacity_path,
        [
            {
                "atc_global_id": "shelter-glob-1",
                "atc_name": "Test Shelter",
                "capacity": None,
                "unresolved": "the source gives 'xxx', which is not a number",
            }
        ],
    )

    monkeypatch.setattr(export_poi, "RAW_DIR", raw_dir)
    monkeypatch.setattr(export_poi, "OUT_DIR", out_dir)
    monkeypatch.setattr(export_poi, "CAPACITY_PATH", capacity_path)

    export_poi.main()

    shelter_props = json.loads((out_dir / "shelter.geojson").read_text())["features"][0]["properties"]
    assert shelter_props.get("capacity") is None


def test_export_poi_exports_without_capacity_when_the_reference_file_is_absent(tmp_path, monkeypatch, con):
    """Same posture as a missing images file: the export ships. A checkout
    that has not got the reference file loses the capacity line, not the
    waypoints."""
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    out_dir = tmp_path / "processed" / "poi"
    _write_fixture_sources(raw_dir)

    monkeypatch.setattr(export_poi, "RAW_DIR", raw_dir)
    monkeypatch.setattr(export_poi, "OUT_DIR", out_dir)
    monkeypatch.setattr(export_poi, "CAPACITY_PATH", tmp_path / "does-not-exist.json")

    manifest = export_poi.main()

    assert manifest["shelter"]["geojson"]["feature_count"] == 1
    shelter_props = json.loads((out_dir / "shelter.geojson").read_text())["features"][0]["properties"]
    assert shelter_props.get("capacity") is None


def test_export_poi_exported_properties_are_exactly_the_declared_columns(tmp_path, monkeypatch, con):
    """POI_COLUMNS is the one list the DDL, the `?` placeholders and the row
    tuple are all built from, and this is what keeps it honest.

    The failure it guards is not a crash. Add a column to the DDL and forget
    the value tuple and every column after it shifts by one - a photo licence
    published as a capacity, valid GeoJSON the whole way. So this pins both
    ends: the property names the driver writes, and that each value landed
    under its own name rather than its neighbour's."""
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    out_dir = tmp_path / "processed" / "poi"
    _write_fixture_sources(raw_dir)
    capacity_path = tmp_path / "shelter_capacity.json"
    _write_capacity_file(capacity_path, [{"atc_global_id": "shelter-glob-1", "atc_name": "Test Shelter", "capacity": 8}])
    (raw_dir / "poi_images.json").write_text(
        json.dumps(
            {
                "pois": {
                    "atc_shelters:shelter-glob-1": {
                        "status": "found",
                        "checked": "2026-08-07",
                        "photo": {
                            "digest": SHELTER_DIGEST,
                            "page_url": "https://commons.wikimedia.org/wiki/File:Test_Shelter.jpg",
                            "author": "Jane Doe",
                            "license": "CC BY-SA 4.0",
                            "taken": "2025-06-18",
                        },
                    }
                }
            }
        )
    )

    monkeypatch.setattr(export_poi, "RAW_DIR", raw_dir)
    monkeypatch.setattr(export_poi, "OUT_DIR", out_dir)
    monkeypatch.setattr(export_poi, "CAPACITY_PATH", capacity_path)

    export_poi.main()

    props = json.loads((out_dir / "shelter.geojson").read_text())["features"][0]["properties"]
    assert set(props) == {name for name, _ in export_poi.POI_COLUMNS}

    # Every column distinguishable from its neighbours, so a one-place shift
    # cannot pass: the capacity sits between `confidence` and `photo_key`,
    # which is exactly where an off-by-one would land the wrong value.
    assert props["confidence"] == CONFIDENCE_HIGH
    assert props["capacity"] == 8
    assert props["photo_key"] == f"photos/{SHELTER_DIGEST}.jpg"
    assert props["photo_author"] == "Jane Doe"
    assert props["name"] == "Test Shelter"
    assert props["source"] == export_poi.SHELTER_SOURCE


def test_export_poi_composes_a_description_for_shelters_and_campsites(tmp_path, monkeypatch, con):
    """ATC publishes no prose description, so the export assembles one from
    its inventory columns (lib/poi_description.py) and folds in the capacity
    the reference file supplies. Water and resupply come from opentrail.org,
    which has no inventory to compose from, and get none."""
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    out_dir = tmp_path / "processed" / "poi"
    _write_fixture_sources(raw_dir)
    capacity_path = tmp_path / "shelter_capacity.json"
    _write_capacity_file(capacity_path, [{"atc_global_id": "shelter-glob-1", "atc_name": "Test Shelter", "capacity": 8}])

    monkeypatch.setattr(export_poi, "RAW_DIR", raw_dir)
    monkeypatch.setattr(export_poi, "OUT_DIR", out_dir)
    monkeypatch.setattr(export_poi, "CAPACITY_PATH", capacity_path)

    export_poi.main()

    shelter_props = json.loads((out_dir / "shelter.geojson").read_text())["features"][0]["properties"]
    # The capacity clause proves the ordering that matters: descriptions are
    # composed after attach_capacity, because the number is not ATC's.
    assert shelter_props["description"] == "Two-storey log shelter, sleeps 8, with a fireplace. Built 1954."

    campsite_props = json.loads((out_dir / "campsite.geojson").read_text())["features"][0]["properties"]
    assert campsite_props["description"] == "Designated campsite, 3 sites."

    water_fc = json.loads((out_dir / "water.geojson").read_text())
    for feature in water_fc["features"]:
        assert feature["properties"].get("description") is None


def test_export_poi_folds_atcs_own_comment_into_the_description(tmp_path, monkeypatch, con):
    """Where ATC wrote something worth reading it is published as theirs.
    Where they wrote a note to the survey it is dropped, and the composed
    sentence stands alone - the shelter does not inherit "Not sure about
    spatial info"."""
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    out_dir = tmp_path / "processed" / "poi"
    _write_fixture_sources(raw_dir)
    _write_fc(
        raw_dir / "shelters.geojson",
        [
            _point_feature(
                1,
                -73.95,
                41.05,
                {"GlobalID": "s1", "Name": "Noted Shelter", "Stories": 1, "Exterior_M": "5", "Comments": "Has a loft"},
            ),
            _point_feature(
                2,
                -73.95,
                41.06,
                {
                    "GlobalID": "s2",
                    "Name": "Surveyed Shelter",
                    "Stories": 1,
                    "Exterior_M": "5",
                    "Comments": "Not sure about spatial info",
                },
            ),
        ],
    )

    monkeypatch.setattr(export_poi, "RAW_DIR", raw_dir)
    monkeypatch.setattr(export_poi, "OUT_DIR", out_dir)

    export_poi.main()

    by_name = {
        f["properties"]["name"]: f["properties"] for f in json.loads((out_dir / "shelter.geojson").read_text())["features"]
    }
    assert by_name["Noted Shelter"]["description"] == "Log shelter. ATC notes: Has a loft."
    assert by_name["Surveyed Shelter"]["description"] == "Log shelter."


def test_export_poi_does_not_publish_the_raw_source_properties(tmp_path, monkeypatch, con):
    """unify_all_sources parks each feature's own ATC attributes on the record
    for attach_descriptions to read. That is scaffolding between two steps,
    and none of ATC's 135 columns may reach the artifact through it."""
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    out_dir = tmp_path / "processed" / "poi"
    _write_fixture_sources(raw_dir)

    monkeypatch.setattr(export_poi, "RAW_DIR", raw_dir)
    monkeypatch.setattr(export_poi, "OUT_DIR", out_dir)

    export_poi.main()

    props = json.loads((out_dir / "shelter.geojson").read_text())["features"][0]["properties"]
    assert export_poi.RAW_PROPERTIES_KEY not in props
    assert set(props) == {name for name, _ in export_poi.POI_COLUMNS}


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
