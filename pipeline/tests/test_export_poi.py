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


def _json_prop(value):
    """A JSON-string column as the thing it holds, whichever shape it arrives in.

    The pipeline writes one string - FlatGeobuf property values are scalars -
    but GDAL recognises a JSON-shaped string when it writes GeoJSON and emits
    real JSON, so `photos` and `nearby` genuinely differ in type between the
    two artifacts of one export (measured 2026-08-09). The client accepts both
    for the same reason, and a test that assumed either would pass on one file
    and fail on the other.
    """
    return json.loads(value) if isinstance(value, str) else value


def _write_fc(path, features):
    path.write_text(json.dumps({"type": "FeatureCollection", "features": features}))


def _write_fixture_sources(raw_dir):
    """Tiny synthetic stand-ins for the seven real raw sources, all placed
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
    # The three facility layers that share ATC's ANST_Facilities schema with
    # shelters and campsites - same GlobalID/Name pair, plus the inventory
    # columns lib/poi_description.py composes each one's sentence from.
    # `Descriptio` is here on the vista holding ATC's real value for it
    # ("TBD" on every one sampled), so nothing can be written against a
    # fixture that is cleaner than the data.
    _write_fc(
        raw_dir / "viewpoints.geojson",
        [
            _point_feature(
                1,
                -73.96,
                41.06,
                {
                    "GlobalID": "viewpoint-glob-1",
                    "OBJECTID": 1,
                    "Name": "Test Vista",
                    "Status": "Primary View",
                    "Descriptio": "TBD",
                    # The columns lib/poi_description.py composes from: the
                    # arc's two bearings and the landform.
                    "Left_Beari": 40,
                    "Right_Bear": 220,
                    "Location": "Mtn/Ridge/Outcrop",
                },
            )
        ],
    )
    _write_fc(
        raw_dir / "parking.geojson",
        [
            _point_feature(
                1,
                -73.97,
                41.07,
                {
                    "GlobalID": "parking-glob-1",
                    "OBJECTID": 1,
                    "Name": "Test Rd Parking Area",
                    "Type": "0",
                    "Surface": "3",
                    "Parking_S": 7,
                    "ADA_Space": 0,
                },
            )
        ],
    )
    _write_fc(
        raw_dir / "privies.geojson",
        [
            _point_feature(
                1,
                -73.98,
                41.08,
                {
                    "GlobalID": "privy-glob-1",
                    "OBJECTID": 1,
                    "Name": "Test Shelter Privy",
                    "Type": "1",
                    "Enclosure": "1",
                    "Year_Built": 2003,
                },
            )
        ],
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


@pytest.fixture(autouse=True)
def no_real_water_distance_file(tmp_path, monkeypatch):
    """WATER_DISTANCE_PATH gets the same treatment as CAPACITY_PATH above,
    for the same reason."""
    monkeypatch.setattr(export_poi, "WATER_DISTANCE_PATH", tmp_path / "no-water-distance-file.json")


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


def _write_water_distance_file(path, records):
    """A stand-in for reference/water_distance.json, same shape
    build_water_distance.py writes."""
    path.write_text(json.dumps({"sites": records}))


def test_export_poi_carries_water_distance_onto_shelters_and_campsites(tmp_path, monkeypatch, con):
    """water_distance.json's numbers reach both layers' features - keyed by
    layer + GlobalID, because the file covers shelters AND campsites - and the
    close one is named among the anchor's nearby parts, so the card answers "is
    there water" without a water point in the data (#668). 120 ft is ~37 m:
    inside NEARBY_WATER_MAX_FT.

    Straight through in ATC's own feet since #625. It used to be converted to
    metres on the way into the sentence, which meant an imperial hiker read a
    figure ATC published in feet, in metres, having asked for feet."""
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    out_dir = tmp_path / "processed" / "poi"
    _write_fixture_sources(raw_dir)
    water_path = tmp_path / "water_distance.json"
    _write_water_distance_file(
        water_path,
        [
            {"layer": "shelters", "atc_global_id": "shelter-glob-1", "distance_ft": 120},
            {"layer": "campsites", "atc_global_id": "campsite-glob-1", "distance_ft": 100},
            # A refusal row, exactly as build_water_distance.py writes one:
            # null distance, reason stated. Must publish nothing.
            {
                "layer": "shelters",
                "atc_global_id": "shelter-glob-absent",
                "distance_ft": None,
                "unresolved": "no CSI row within 150 m",
            },
        ],
    )

    monkeypatch.setattr(export_poi, "RAW_DIR", raw_dir)
    monkeypatch.setattr(export_poi, "OUT_DIR", out_dir)
    monkeypatch.setattr(export_poi, "WATER_DISTANCE_PATH", water_path)

    export_poi.main()

    shelter_props = json.loads((out_dir / "shelter.geojson").read_text())["features"][0]["properties"]
    assert shelter_props["water_distance_ft"] == 120
    # The column's own number, unconverted, through the same nearby_parts a
    # folded water point would use - so one card cannot say it two ways.
    assert _json_prop(shelter_props["nearby"]) == [{"phrase": "water", "distance_ft": 120.0}]

    campsite_props = json.loads((out_dir / "campsite.geojson").read_text())["features"][0]["properties"]
    assert campsite_props["water_distance_ft"] == 100
    assert _json_prop(campsite_props["nearby"]) == [{"phrase": "water", "distance_ft": 100.0}]

    # Real water POIs never carry the column - it is a fact about a shelter
    # or campsite, not about the water point itself. The members synthesized
    # from those distances (#694) are the one exception: they ARE the number,
    # carried so the card's chip can print it instead of measuring their
    # inherited coordinates to zero.
    water_fc = json.loads((out_dir / "water.geojson").read_text())
    for feature in water_fc["features"]:
        if feature["properties"]["source"] != export_poi.CSI_WATER_SOURCE:
            assert feature["properties"].get("water_distance_ft") is None


def test_export_poi_synthesizes_a_water_member_where_the_sentence_fired(tmp_path, monkeypatch, con):
    """The card promising water gets a water POI riding its site (#694): a
    member at the anchor's own coordinates - ATC states how far, never where -
    whose description says whose measurement the distance is and that the spot
    is unmapped. The anchor becomes a site so the pin has a strip for the
    glyph, and its own nearby entry still carries the stated distance, never
    the member's inherited position ("water 3 ft" is the bug this arrangement
    exists to not have).

    The figure itself is NOT in the description, since #625: it is published on
    this member as `water_distance_ft`, so the chip beside the sentence prints
    it in the units the hiker chose. A distance written into published prose is
    a distance in somebody else's units."""
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    out_dir = tmp_path / "processed" / "poi"
    _write_fixture_sources(raw_dir)
    water_path = tmp_path / "water_distance.json"
    _write_water_distance_file(water_path, [{"layer": "shelters", "atc_global_id": "shelter-glob-1", "distance_ft": 120}])

    monkeypatch.setattr(export_poi, "RAW_DIR", raw_dir)
    monkeypatch.setattr(export_poi, "OUT_DIR", out_dir)
    monkeypatch.setattr(export_poi, "WATER_DISTANCE_PATH", water_path)

    export_poi.main()

    shelter_props = json.loads((out_dir / "shelter.geojson").read_text())["features"][0]["properties"]
    water_fc = json.loads((out_dir / "water.geojson").read_text())
    [synthesized] = [f["properties"] for f in water_fc["features"] if f["properties"]["source"] == export_poi.CSI_WATER_SOURCE]

    assert synthesized["id"] == "atc_csi:shelter-glob-1"
    assert synthesized["name"] == "Water near Test Shelter"
    assert synthesized["confidence"] == "low"
    assert synthesized["water_distance_ft"] == 120
    # Inherited coordinates, and a description that says so in place of them.
    assert (synthesized["lat"], synthesized["lon"]) == (shelter_props["lat"], shelter_props["lon"])
    assert synthesized["description"] == (
        "ATC measured how far water is from Test Shelter; the spot itself is not mapped, so this point sits on the shelter."
    )
    # And no figure in it, in either unit - the chip carries that (#625).
    assert not any(character.isdigit() for character in synthesized["description"])
    # It rides the shelter's site as a member, and the lone shelter became a
    # site to carry it.
    assert synthesized["site_id"] == shelter_props["id"]
    assert synthesized["site_role"] == "member"
    assert shelter_props["site_role"] == "anchor"
    assert shelter_props["site_id"] == shelter_props["id"]
    # The anchor's own parts still carry the stated distance, not the zero its
    # member's inherited position would measure.
    assert _json_prop(shelter_props["nearby"]) == [{"phrase": "water", "distance_ft": 120.0}]


def test_export_poi_synthesizes_from_the_anchor_only_never_from_a_member(tmp_path, monkeypatch, con):
    """A campsite folded into a shelter's site carries the column but spawns
    nothing: the site already answers "is there water" through its anchor,
    and two synthesized members for one place would be the pin saying water
    twice."""
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    out_dir = tmp_path / "processed" / "poi"
    _write_fixture_sources(raw_dir)
    # ATC's naming convention, close enough to fold: the campsite becomes a
    # member of the shelter's site (name gate, well under 150 m).
    _write_fc(
        raw_dir / "campsites.geojson",
        [_point_feature(1, -73.95, 41.0504, {"GlobalID": "campsite-glob-1", "Name": "Test Shelter Campsite", "Site_Num": 3})],
    )
    water_path = tmp_path / "water_distance.json"
    _write_water_distance_file(
        water_path,
        [
            {"layer": "shelters", "atc_global_id": "shelter-glob-1", "distance_ft": 120},
            {"layer": "campsites", "atc_global_id": "campsite-glob-1", "distance_ft": 100},
        ],
    )

    monkeypatch.setattr(export_poi, "RAW_DIR", raw_dir)
    monkeypatch.setattr(export_poi, "OUT_DIR", out_dir)
    monkeypatch.setattr(export_poi, "WATER_DISTANCE_PATH", water_path)

    export_poi.main()

    water_fc = json.loads((out_dir / "water.geojson").read_text())
    synthesized = [f["properties"] for f in water_fc["features"] if f["properties"]["source"] == export_poi.CSI_WATER_SOURCE]
    assert [record["id"] for record in synthesized] == ["atc_csi:shelter-glob-1"]


def test_export_poi_keeps_far_water_out_of_the_nearby_sentence(tmp_path, monkeypatch, con):
    """Blood Mtn Shelter's real number is 1,648 ft - about 500 m. The column
    publishes it (a far distance is exactly what a hiker at a famously dry
    shelter needs), but "Nearby" is a word the site vocabulary already
    defines as within NAME_MATCH_RADIUS_M, and this sentence must not stretch
    it. WATER_SOURCES.md's honesty rule: true silence beats a false comfort."""
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    out_dir = tmp_path / "processed" / "poi"
    _write_fixture_sources(raw_dir)
    water_path = tmp_path / "water_distance.json"
    _write_water_distance_file(water_path, [{"layer": "shelters", "atc_global_id": "shelter-glob-1", "distance_ft": 1648}])

    monkeypatch.setattr(export_poi, "RAW_DIR", raw_dir)
    monkeypatch.setattr(export_poi, "OUT_DIR", out_dir)
    monkeypatch.setattr(export_poi, "WATER_DISTANCE_PATH", water_path)

    export_poi.main()

    shelter_props = json.loads((out_dir / "shelter.geojson").read_text())["features"][0]["properties"]
    assert shelter_props["water_distance_ft"] == 1648
    assert "water" not in shelter_props["description"]
    # And no synthesized member either (#694): a site is a sub-150 m place,
    # and a part half a kilometre off is not a part of it.
    water_fc = json.loads((out_dir / "water.geojson").read_text())
    assert not [f for f in water_fc["features"] if f["properties"]["source"] == export_poi.CSI_WATER_SOURCE]


def test_export_poi_never_says_water_twice_when_a_real_point_already_folded(tmp_path, monkeypatch, con):
    """A site whose parts already name an actual folded water point keeps that
    measured distance - the CSI estimate stays out, because one card naming two
    water distances reads as two waters and is really one disagreement. The
    column still publishes; the two numbers remain distinguishable by where
    they appear."""
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    out_dir = tmp_path / "processed" / "poi"
    _write_fixture_sources(raw_dir)
    # A water point ~44 m from Test Shelter: inside PROXIMITY_RADIUS_M, so it
    # folds into the shelter's site as a member and the clause names it.
    _write_fc(
        raw_dir / "opentrail_at.geojson",
        [_point_feature(0, -73.95, 41.0504, {"title": "Test Spring", "icon": "w", "dbid": 100})],
    )
    water_path = tmp_path / "water_distance.json"
    _write_water_distance_file(water_path, [{"layer": "shelters", "atc_global_id": "shelter-glob-1", "distance_ft": 120}])

    monkeypatch.setattr(export_poi, "RAW_DIR", raw_dir)
    monkeypatch.setattr(export_poi, "OUT_DIR", out_dir)
    monkeypatch.setattr(export_poi, "WATER_DISTANCE_PATH", water_path)

    export_poi.main()

    shelter_props = json.loads((out_dir / "shelter.geojson").read_text())["features"][0]["properties"]
    assert shelter_props["water_distance_ft"] == 120
    waters = [part for part in _json_prop(shelter_props["nearby"]) if part["phrase"] == "water"]
    assert len(waters) == 1
    # The folded point's own measurement - ~45 m, so ~147 ft - and not the
    # reference file's 120 ft.
    assert waters[0]["distance_ft"] == pytest.approx(147, abs=2)
    # And no synthesized member beside the real one (#694): the site already
    # holds an actual mapped point, and it speaks for water here.
    water_fc = json.loads((out_dir / "water.geojson").read_text())
    assert not [f for f in water_fc["features"] if f["properties"]["source"] == export_poi.CSI_WATER_SOURCE]


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
    # The column between capacity and description: present as a key, NULL
    # with no reference file - so a one-place shift cannot hide in it.
    assert props.get("water_distance_ft") is None
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


def test_export_poi_publishes_atcs_vistas_parking_and_privies_as_their_own_types(tmp_path, monkeypatch, con):
    """The three facility layers sources.json has carried since 2026-07-25.

    Asserted through the real export rather than through DIRECT_SOURCES,
    because the failure this guards against is not a missing tuple - it is a
    layer wired up under a source name the ids are not composed from, which
    reads as working right up until a Report or a spur destination tries to
    resolve one.
    """
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    out_dir = tmp_path / "processed" / "poi"
    _write_fixture_sources(raw_dir)

    monkeypatch.setattr(export_poi, "RAW_DIR", raw_dir)
    monkeypatch.setattr(export_poi, "OUT_DIR", out_dir)

    export_poi.main()

    expected = {
        "viewpoint": ("Test Vista", "atc_viewpoints:viewpoint-glob-1"),
        "parking": ("Test Rd Parking Area", "atc_parking:parking-glob-1"),
        "privy": ("Test Shelter Privy", "atc_privies:privy-glob-1"),
    }
    for poi_type, (name, poi_id) in expected.items():
        features = json.loads((out_dir / f"{poi_type}.geojson").read_text())["features"]
        assert len(features) == 1, poi_type
        properties = features[0]["properties"]
        assert properties["id"] == poi_id
        assert properties["name"] == name
        assert properties["poi_type"] == poi_type
        # ATC's own inventory of what ATC maintains, the same standing its
        # shelters and campsites have - not the Communities-layer proxy.
        assert properties["confidence"] == CONFIDENCE_HIGH


def test_export_poi_composes_a_description_for_every_atc_facility_type(tmp_path, monkeypatch, con):
    """`description` is composed for all five ATC layers, not copied.

    ATC's `Descriptio` column on these is the club acronym plus the feature's
    own name (and literally "TBD" on the vistas), which lib/atc_notes.py
    measured as unusable - so each sentence is assembled from the inventory
    columns instead, and the assertion is on the sentence rather than on the
    field being non-empty: a wiring mistake that composed a vista's sentence
    for a privy would pass the weaker check.
    """
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    out_dir = tmp_path / "processed" / "poi"
    _write_fixture_sources(raw_dir)

    monkeypatch.setattr(export_poi, "RAW_DIR", raw_dir)
    monkeypatch.setattr(export_poi, "OUT_DIR", out_dir)

    export_poi.main()

    expected = {
        "viewpoint": "A 180° view south-east from a ridge or rock outcrop.",
        "parking": "Gravel parking area, room for 7 cars.",
        "privy": "Moldering privy. Built 2003.",
    }
    for poi_type, sentence in expected.items():
        features = json.loads((out_dir / f"{poi_type}.geojson").read_text())["features"]
        assert features[0]["properties"]["description"] == sentence


def test_export_poi_leaves_the_types_with_no_inventory_behind_them_undescribed(tmp_path, monkeypatch, con):
    """Water and resupply compose nothing, and that is the honest export.

    They come from opentrail.org's tags and ATC's Communities layer, neither
    of which carries an inventory to assemble a sentence from. A describer
    added for them would have to invent its material.
    """
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    out_dir = tmp_path / "processed" / "poi"
    _write_fixture_sources(raw_dir)

    monkeypatch.setattr(export_poi, "RAW_DIR", raw_dir)
    monkeypatch.setattr(export_poi, "OUT_DIR", out_dir)

    export_poi.main()

    for poi_type in ("water", "resupply"):
        features = json.loads((out_dir / f"{poi_type}.geojson").read_text())["features"]
        assert all(feature["properties"].get("description") is None for feature in features), poi_type


def test_export_poi_publishes_every_photo_as_json_alongside_the_flat_card_fields(tmp_path, monkeypatch, con):
    """A POI with several photos exports the whole list, and still exports the
    first one through the flat photo_* fields.

    Both shapes, deliberately. FlatGeobuf property values are scalars, so the
    list can only travel as a JSON string - and a client built before
    galleries existed reads only the flat fields, so dropping them would blank
    the card on every already-installed app instead of adding to it."""
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    out_dir = tmp_path / "processed" / "poi"
    _write_fixture_sources(raw_dir)
    second_digest = "b" * 64
    (raw_dir / "poi_images_atc.json").write_text(
        json.dumps(
            {
                "pois": {
                    "atc_shelters:shelter-glob-1": {
                        "status": "found",
                        "checked": "2026-08-09",
                        "photos": [
                            {
                                "digest": SHELTER_DIGEST,
                                "page_url": "https://drive.google.com/file/d/one/view",
                                "author": "Appalachian Trail Conservancy",
                                "license": "© ATC, used with permission",
                                "taken": "2016-09-12",
                            },
                            {
                                "digest": second_digest,
                                "page_url": "https://drive.google.com/file/d/two/view",
                                "author": "Appalachian Trail Conservancy",
                                "license": "© ATC, used with permission",
                                "taken": "2016-09-13",
                            },
                            # No digest: nothing names it in the bucket, so it
                            # must not reach the artifact even inside a list.
                            {"page_url": "https://drive.google.com/file/d/three/view", "taken": "2016-09-14"},
                        ],
                    }
                }
            }
        )
    )

    monkeypatch.setattr(export_poi, "RAW_DIR", raw_dir)
    monkeypatch.setattr(export_poi, "OUT_DIR", out_dir)
    export_poi.main()

    shelters = json.loads((out_dir / "shelter.geojson").read_text())["features"]
    props = next(f["properties"] for f in shelters if f["properties"]["id"] == "atc_shelters:shelter-glob-1")

    assert props["photo_key"] == f"photos/{SHELTER_DIGEST}.jpg"
    assert props["photo_taken"] == "2016-09-12"

    # GDAL emits the pipeline's JSON string as real JSON when writing GeoJSON
    # and leaves it a string in the .fgb - same export, two shapes (measured
    # 2026-08-09), which is why the client accepts both.
    photos = props["photos"] if isinstance(props["photos"], list) else json.loads(props["photos"])
    assert [p["key"] for p in photos] == [f"photos/{SHELTER_DIGEST}.jpg", f"photos/{second_digest}.jpg"]
    assert photos[0]["author"] == "Appalachian Trail Conservancy"
    assert photos[1]["taken"] == "2016-09-13"


def test_export_poi_reads_the_single_photo_shape_the_commons_fetch_writes(tmp_path, monkeypatch, con):
    """fetch_poi_images.py records one `photo` per POI and fetch_atc_photos.py
    records a `photos` list. Both must export, or the Commons source silently
    stops filling water and resupply."""
    records = export_poi.load_photo_records.__wrapped__ if hasattr(export_poi.load_photo_records, "__wrapped__") else None
    assert records is None  # plain function, no decorator - guard against a silent refactor

    path = tmp_path / "poi_images.json"
    path.write_text(
        json.dumps(
            {
                "pois": {
                    "a": {"status": "found", "photo": {"digest": "a" * 64, "taken": "2025-01-01"}},
                    "b": {"status": "found", "photos": [{"digest": "b" * 64}, {"digest": "c" * 64}]},
                    "c": {"status": "none"},
                }
            }
        )
    )

    loaded = export_poi.load_photo_records(path)

    assert [p["digest"] for p in loaded["a"]] == ["a" * 64]
    assert [p["digest"] for p in loaded["b"]] == ["b" * 64, "c" * 64]
    assert "c" not in loaded


def test_the_photo_list_survives_both_artifact_formats(tmp_path, monkeypatch, con):
    """The two formats disagree about this field's type, and that is the whole
    reason this test exists.

    The pipeline writes one JSON *string*, because FlatGeobuf property values
    are scalars and a nested array cannot be a column. GDAL then recognises a
    JSON-shaped string when writing GeoJSON and emits real JSON, while the
    .fgb keeps the string. Measured 2026-08-09; the client accepts both
    because of it. If a GDAL upgrade ever makes the two agree, this test says
    so out loud rather than the client quietly reading nothing."""
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    out_dir = tmp_path / "processed" / "poi"
    _write_fixture_sources(raw_dir)
    second_digest = "d" * 64
    (raw_dir / "poi_images_atc.json").write_text(
        json.dumps(
            {
                "pois": {
                    "atc_shelters:shelter-glob-1": {
                        "status": "found",
                        "photos": [
                            {"digest": SHELTER_DIGEST, "taken": "2016-09-12"},
                            {"digest": second_digest, "taken": "2016-09-13"},
                        ],
                    }
                }
            }
        )
    )
    monkeypatch.setattr(export_poi, "RAW_DIR", raw_dir)
    monkeypatch.setattr(export_poi, "OUT_DIR", out_dir)
    export_poi.main()

    geojson_value = next(
        f["properties"]["photos"]
        for f in json.loads((out_dir / "shelter.geojson").read_text())["features"]
        if f["properties"]["id"] == "atc_shelters:shelter-glob-1"
    )
    fgb_value = con.execute(
        f"SELECT photos FROM st_read('{out_dir / 'shelter.fgb'}') WHERE id = 'atc_shelters:shelter-glob-1'"
    ).fetchone()[0]

    from_geojson = geojson_value if isinstance(geojson_value, list) else json.loads(geojson_value)
    from_fgb = fgb_value if isinstance(fgb_value, list) else json.loads(fgb_value)

    # Whatever the wire types, both artifacts must describe the same photos.
    assert [p["key"] for p in from_geojson] == [f"photos/{SHELTER_DIGEST}.jpg", f"photos/{second_digest}.jpg"]
    assert from_geojson == from_fgb


def test_export_poi_skips_a_source_row_that_has_no_geometry(tmp_path, monkeypatch, con):
    """The outage this guards against, and it is not hypothetical.

    ATC's parking layer carries exactly one empty row - GlobalID
    ebb7706f-ed9a-432e-87b1-8d949917f66c, no name, no attributes, no
    geometry - out of 2,533 features across all five facility layers. Before
    this, `unify_poi` raised on it and the whole export died, taking every
    artifact of the release behind it: a single blank row upstream meant no
    data release at all.

    A feature with no geometry is not a POI. It cannot be drawn, found by
    search or reported against, and verify_release.py fails a release that
    publishes one. Skipping it is the honest handling; the rest of the layer
    still ships.
    """
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    out_dir = tmp_path / "processed" / "poi"
    _write_fixture_sources(raw_dir)
    _write_fc(
        raw_dir / "parking.geojson",
        [
            _point_feature(1, -73.97, 41.07, {"GlobalID": "parking-glob-1", "Name": "Test Rd Parking Area", "Surface": "3"}),
            {"type": "Feature", "id": 2, "geometry": None, "properties": {"GlobalID": "parking-empty"}},
        ],
    )

    monkeypatch.setattr(export_poi, "RAW_DIR", raw_dir)
    monkeypatch.setattr(export_poi, "OUT_DIR", out_dir)

    manifest = export_poi.main()

    assert manifest["parking"]["geojson"]["feature_count"] == 1
    features = json.loads((out_dir / "parking.geojson").read_text())["features"]
    assert [f["properties"]["id"] for f in features] == ["atc_parking:parking-glob-1"]


def test_export_poi_reports_which_rows_it_skipped(tmp_path, monkeypatch):
    """Counted and named rather than dropped quietly: one empty row is ATC's
    long-standing data, and a number that grows is a source going wrong."""
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    _write_fixture_sources(raw_dir)
    _write_fc(
        raw_dir / "privies.geojson",
        [{"type": "Feature", "id": 1, "geometry": None, "properties": {"GlobalID": "privy-empty"}}],
    )

    monkeypatch.setattr(export_poi, "RAW_DIR", raw_dir)
    skipped: list[str] = []

    export_poi.unify_all_sources("AT", skipped)

    assert skipped == ["atc_privies:privy-empty"]


def test_export_poi_still_refuses_a_geometry_that_is_the_wrong_shape(tmp_path, monkeypatch):
    """The other half of the split. A missing geometry is bad data upstream;
    a polygon where points were expected is the wrong layer wired into a
    point source, and that must not be absorbed as "one row skipped" - it
    would empty a whole poi_type silently."""
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    _write_fixture_sources(raw_dir)
    _write_fc(
        raw_dir / "privies.geojson",
        [
            {
                "type": "Feature",
                "id": 1,
                "geometry": {"type": "Polygon", "coordinates": [[[-73.9, 41.0], [-73.8, 41.0], [-73.8, 41.1]]]},
                "properties": {"GlobalID": "privy-polygon"},
            }
        ],
    )

    monkeypatch.setattr(export_poi, "RAW_DIR", raw_dir)

    with pytest.raises(ValueError, match="only supports Point geometries"):
        export_poi.unify_all_sources("AT", [])


# --- the preflight ---------------------------------------------------------


def test_check_reads_the_sources_and_writes_nothing(tmp_path, monkeypatch, con):
    """`--check` is what the publish workflow runs before an hour of photo
    fetching. It must exercise the real reading path and leave no artifact
    behind - an export that half-wrote its output on a preflight would be
    worse than no preflight."""
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    out_dir = tmp_path / "processed" / "poi"
    _write_fixture_sources(raw_dir)

    monkeypatch.setattr(export_poi, "RAW_DIR", raw_dir)
    monkeypatch.setattr(export_poi, "OUT_DIR", out_dir)

    counts = export_poi.check_sources()

    assert counts == {
        "shelter": 1,
        "campsite": 1,
        "water": 2,
        "resupply": 2,
        "crossing": 0,
        "viewpoint": 1,
        "parking": 1,
        "privy": 1,
    }
    assert not out_dir.exists()


def test_check_fails_on_the_defect_that_would_otherwise_surface_an_hour_later(tmp_path, monkeypatch):
    """A source that came back without its features. Caught here, it costs
    seconds; caught in the export, it costs the photo fetch that ran in
    between - which is the whole argument for the step existing."""
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    _write_fixture_sources(raw_dir)
    _write_fc(raw_dir / "viewpoints.geojson", [])

    monkeypatch.setattr(export_poi, "RAW_DIR", raw_dir)

    with pytest.raises(SystemExit) as exc_info:
        export_poi.check_sources()

    assert exc_info.value.code == 1


def test_check_and_the_export_gate_on_the_same_rule(tmp_path, monkeypatch, con):
    """The preflight would be worth little if it were more lenient than the
    export it stands in for. Both call fail_if_any_type_is_empty, and
    `crossing` is the one type allowed to be empty in both."""
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    out_dir = tmp_path / "processed" / "poi"
    _write_fixture_sources(raw_dir)

    monkeypatch.setattr(export_poi, "RAW_DIR", raw_dir)
    monkeypatch.setattr(export_poi, "OUT_DIR", out_dir)

    # crossing is empty in the fixtures, and neither side objects.
    assert export_poi.check_sources()["crossing"] == 0
    assert export_poi.main()["crossing"]["geojson"]["feature_count"] == 0


def test_an_unknown_flag_is_rejected_rather_than_silently_exporting(monkeypatch, capsys):
    """A typo'd `--check` must not run the full export in a step that asked
    for a preflight - it would write artifacts from unfetched photos."""
    monkeypatch.setattr(export_poi, "main", lambda: pytest.fail("main() ran for an unknown flag"))

    with pytest.raises(SystemExit) as exc_info:
        export_poi.run(["--chekc"])

    assert exc_info.value.code == 2
    assert "Unknown flag" in capsys.readouterr().out


def test_export_poi_publishes_the_site_grouping_on_the_features(tmp_path, monkeypatch, con):
    """A shelter and its privy are published as one place with parts (#523).

    The fixture privy sits 3.8 km from the fixture shelter - far outside both
    gates - so the shared fixtures produce no site at all. The privy is
    re-written 42 m out, which is the corridor's measured median privy-to-shelter
    distance, so this exercises the grouping rather than the empty case.
    """
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    out_dir = tmp_path / "processed" / "poi"
    _write_fixture_sources(raw_dir)
    _write_fc(
        raw_dir / "privies.geojson",
        [
            _point_feature(
                1,
                -73.95,
                # 42 m north of the shelter at 41.05.
                41.05 + 42 / 111_320.0,
                {
                    "GlobalID": "privy-glob-1",
                    "OBJECTID": 1,
                    "Name": "Test Shelter Privy",
                    "Type": "1",
                    "Enclosure": "1",
                    "Year_Built": 2003,
                },
            )
        ],
    )

    monkeypatch.setattr(export_poi, "RAW_DIR", raw_dir)
    monkeypatch.setattr(export_poi, "OUT_DIR", out_dir)

    export_poi.main()

    shelter = json.loads((out_dir / "shelter.geojson").read_text())["features"][0]["properties"]
    privy = json.loads((out_dir / "privy.geojson").read_text())["features"][0]["properties"]

    # The anchor's own id is the site id - never a minted one, because a site is
    # what a report or a closure references.
    assert shelter["site_id"] == f"{export_poi.SHELTER_SOURCE}:shelter-glob-1"
    assert shelter["site_role"] == "anchor"
    assert shelter["site_name"] == "Test Shelter"

    # The privy rides the shelter's pin, and carries the shelter's name so the
    # client can label the site without joining anything.
    assert privy["site_id"] == shelter["site_id"]
    assert privy["site_role"] == "member"
    assert privy["site_name"] == "Test Shelter"


def test_export_poi_leaves_the_site_properties_null_outside_a_site(tmp_path, monkeypatch, con):
    """Additive, which is the whole reason these are properties on the existing
    features rather than a second artifact: a POI in no site carries NULL, and a
    client built before #523 ignores the columns and behaves exactly as it does
    today - the same rule `mile`, `capacity`, `description` and `photos` are
    held to."""
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    out_dir = tmp_path / "processed" / "poi"
    _write_fixture_sources(raw_dir)

    monkeypatch.setattr(export_poi, "RAW_DIR", raw_dir)
    monkeypatch.setattr(export_poi, "OUT_DIR", out_dir)

    export_poi.main()

    # A viewpoint can never be a site member at all, and the shared fixtures'
    # privy is kilometres from its shelter, so neither is in one.
    for poi_type in ("viewpoint", "privy"):
        for feature in json.loads((out_dir / f"{poi_type}.geojson").read_text())["features"]:
            assert feature["properties"].get("site_id") is None
            assert feature["properties"].get("site_role") is None
            assert feature["properties"].get("site_name") is None


def test_export_poi_names_a_sites_parts_in_the_anchors_description(tmp_path, monkeypatch, con):
    """A site's anchor publishes what is around it and how far (#614, #625).

    Since #524 the privy draws no pin of its own, so its own perfectly good
    sentence is attached to a feature nothing renders. The anchor's `nearby` is
    where it is named instead.

    The shared fixtures' privy sits 3.8 km from the shelter - outside both
    gates, so no site at all - and is re-written 42 m out, the corridor's
    measured median privy-to-shelter distance. 42 m is 137.8 ft, which is what
    the artifact states: the measurement is metres, the published unit is feet.
    """
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    out_dir = tmp_path / "processed" / "poi"
    _write_fixture_sources(raw_dir)
    _write_fc(
        raw_dir / "privies.geojson",
        [
            _point_feature(
                1,
                -73.95,
                # 42 m north of the shelter at 41.05.
                41.05 + 42 / 111_320.0,
                {
                    "GlobalID": "privy-glob-1",
                    "OBJECTID": 1,
                    "Name": "Test Shelter Privy",
                    "Type": "1",
                    "Enclosure": "2",
                    "Year_Built": 2003,
                },
            )
        ],
    )
    capacity_path = tmp_path / "shelter_capacity.json"
    _write_capacity_file(capacity_path, [{"atc_global_id": "shelter-glob-1", "atc_name": "Test Shelter", "capacity": 8}])

    monkeypatch.setattr(export_poi, "RAW_DIR", raw_dir)
    monkeypatch.setattr(export_poi, "OUT_DIR", out_dir)
    monkeypatch.setattr(export_poi, "CAPACITY_PATH", capacity_path)

    export_poi.main()

    shelter = json.loads((out_dir / "shelter.geojson").read_text())["features"][0]["properties"]
    # The sentence says nothing about the parts since #625 - they are their own
    # column, and their own line on the card, in the hiker's own units.
    assert shelter["description"] == "Two-storey log shelter, sleeps 8, with a fireplace. Built 1954."
    assert _json_prop(shelter["nearby"]) == [{"phrase": "a multi-seat moldering privy", "distance_ft": 137.8}]

    # The member keeps its own sentence, unchanged. It is the thing #526's chip
    # opens, and a member that described itself in terms of its anchor would
    # say the same fact twice on one card.
    privy = json.loads((out_dir / "privy.geojson").read_text())["features"][0]["properties"]
    assert privy["description"] == "Multi-seat moldering privy. Built 2003."


def test_export_poi_leaves_a_description_alone_outside_a_site(tmp_path, monkeypatch, con):
    """Most POIs take this path - 719 of the corridor's points carry site
    properties and the rest do not - and a byte of drift here would rewrite
    artifacts for nothing, which verify_release.py compares hashes to catch."""
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    out_dir = tmp_path / "processed" / "poi"
    _write_fixture_sources(raw_dir)

    monkeypatch.setattr(export_poi, "RAW_DIR", raw_dir)
    monkeypatch.setattr(export_poi, "OUT_DIR", out_dir)

    export_poi.main()

    # The shared fixtures' privy is kilometres from its shelter, so nothing
    # here is in a site at all.
    shelter = json.loads((out_dir / "shelter.geojson").read_text())["features"][0]["properties"]
    assert shelter["description"] == "Two-storey log shelter, with a fireplace. Built 1954."
    assert "Nearby" not in shelter["description"]


def test_export_poi_measures_a_part_from_the_anchor_it_rides():
    """The same equirectangular distance lib/poi_sites.py gated the grouping
    on. Two formulas for one pair would print two numbers for it on one card -
    the client's own siteDistanceFeet is a copy of this one for that reason.

    Converted to feet at this boundary and nowhere else: 42 m is 137.795 ft,
    published to a tenth so the phone rounds once, in whichever unit the hiker
    picked."""
    anchor = {"id": "a", "poi_type": "shelter", "lat": 41.05, "lon": -73.95, "site_id": "a", "site_role": "anchor"}
    member = {
        "id": "b",
        "poi_type": "privy",
        "lat": 41.05 + 42 / 111_320.0,
        "lon": -73.95,
        "site_id": "a",
        "site_role": "member",
    }

    export_poi.attach_nearby([anchor, member])

    assert json.loads(anchor["nearby"]) == [{"phrase": "a privy", "distance_ft": 137.8}]


def test_export_poi_publishes_no_parts_when_the_grouping_never_ran():
    """attach_nearby reads the site properties attach_sites publishes, so a
    caller that skipped the grouping gets no column rather than an error - and
    attach_descriptions, which no longer knows about parts at all, composes
    exactly the sentences it composed before sites existed."""
    raw = export_poi.RAW_PROPERTIES_KEY
    records = [
        {"id": "a", "poi_type": "shelter", "lat": 41.05, "lon": -73.95, raw: {"Stories": 2, "Exterior_M": "5"}},
        {"id": "b", "poi_type": "privy", "lat": 41.05, "lon": -73.95, raw: {"Type": "1"}},
    ]

    assert export_poi.attach_nearby(records) == 0
    export_poi.attach_descriptions(records)

    assert records[0]["description"] == "Two-storey log shelter."
    assert records[1]["description"] == "Moldering privy."
    assert all("nearby" not in record for record in records)


def test_export_poi_leaves_the_sentence_to_the_describer_and_the_parts_to_the_column():
    """#625's split, asserted as the two passes it is.

    A shelter ATC states nothing about used to be kept alive by its parts:
    "Shelter." alone is dropped as saying nothing the type line does not, but
    "Shelter. Nearby: a privy 42 m away." carried. The parts are their own line
    on the card now, so the lead-in has nothing to lead into and the empty
    sentence goes - while the privy is still named, in the hiker's units."""
    anchor = {"id": "a", "poi_type": "shelter", "lat": 41.05, "lon": -73.95, "site_id": "a", "site_role": "anchor"}
    member = {
        "id": "b",
        "poi_type": "privy",
        "lat": 41.05 + 42 / 111_320.0,
        "lon": -73.95,
        "site_id": "a",
        "site_role": "member",
    }

    export_poi.attach_descriptions([anchor, member])
    export_poi.attach_nearby([anchor, member])

    assert "description" not in anchor
    assert json.loads(anchor["nearby"]) == [{"phrase": "a privy", "distance_ft": 137.8}]
