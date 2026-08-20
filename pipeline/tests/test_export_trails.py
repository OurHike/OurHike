"""Tests for export_trails.py - the trail-line export step (ROADMAP.md/
features/TRAIL_BLAZE_COLORS.md): normalize every line source's raw blaze
value into one `blaze_color` attribute (lib/blaze.py), corridor-clip, and
write one combined GeoJSON + FlatGeobuf artifact. Small synthetic fixtures
throughout (tiny GeoJSON built in test code), never the real 3,025+1,200
feature ATC data or a live network call - see TESTING.md.
"""

import hashlib
import json
import math
from pathlib import Path

import pytest
from shapely.geometry import LineString, shape
from shapely.ops import transform as shapely_transform

import export_trails
from tests.conftest import spatial_connection

LAYER_URL = "https://services1.arcgis.com/fake/arcgis/rest/services/Fake/FeatureServer/6"

# Same neighborhood other synthetic fixtures in this suite use (see
# test_spike_corridor.py, test_export_poi.py) - far from any real data, so it
# can't collide with anything.
CENTERLINE_COORDS = [(-74.0, 41.0), (-73.9, 41.1)]
NEAR_COORDS = [(-73.95, 41.05), (-73.94, 41.06)]  # close to the centerline above
FAR_COORDS = [(-70.0, 38.0), (-70.01, 38.01)]  # far outside any sane corridor

# Mirrors side_trails' real ArcGIS field metadata for `Blaze` (confirmed live
# 2026-07-28): esriFieldTypeString with a codedValue domain whose codes are
# themselves strings ("0".."9"), not integers - the raw feature values in the
# real downloaded side_trails.geojson are the string "1", "3", etc, not the
# int 1, 3. Using string codes here (not int, unlike test_lib_arcgis.py's
# generic mock) matches what the real service actually returns.
BLAZE_DOMAIN_RESPONSE = {
    "fields": [
        {
            "name": "Blaze",
            "type": "esriFieldTypeString",
            "alias": "Blaze",
            "domain": {
                "type": "codedValue",
                "name": "Trail Blaze Color",
                "codedValues": [
                    {"name": "None", "code": "0"},
                    {"name": "Blue", "code": "1"},
                    {"name": "White", "code": "2"},
                    {"name": "Red", "code": "3"},
                    {"name": "Other", "code": "9"},
                ],
            },
        }
    ]
}


def _line_feature(coords, properties, feature_id=1):
    return {
        "type": "Feature",
        "id": feature_id,
        "geometry": {"type": "LineString", "coordinates": [[lon, lat] for lon, lat in coords]},
        "properties": properties,
    }


def _write_fc(path, features):
    path.write_text(json.dumps({"type": "FeatureCollection", "features": features}))


def _write_centerline(path, coords=CENTERLINE_COORDS):
    _write_fc(path, [_line_feature(coords, {"GlobalID": "centerline-1", "Name": "A.T."})])


def _write_sources_json(path, sources):
    path.write_text(json.dumps({"_comment": "test fixture", "sources": sources}))


def _centerline_source():
    return {"key": "centerline", "title": "A.T. Centerline", "url": "https://example.test/centerline", "blaze_default": "White"}


def _side_trails_source():
    return {"key": "side_trails", "title": "A.T. Side Trails", "url": LAYER_URL, "blaze_field": "Blaze"}


@pytest.fixture
def con():
    return spatial_connection()


def _run_export(tmp_path, monkeypatch, sources):
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    out_dir = tmp_path / "processed"
    sources_path = tmp_path / "sources.json"
    _write_sources_json(sources_path, sources)

    monkeypatch.setattr(export_trails, "RAW_DIR", raw_dir)
    monkeypatch.setattr(export_trails, "OUT_DIR", out_dir)
    monkeypatch.setattr(export_trails, "SOURCES_PATH", sources_path)
    return raw_dir, out_dir


def test_export_trails_decodes_side_trails_blaze_field_via_the_real_coded_domain(tmp_path, monkeypatch, requests_mock, con):
    raw_dir, out_dir = _run_export(tmp_path, monkeypatch, [_centerline_source(), _side_trails_source()])
    requests_mock.get(LAYER_URL, json=BLAZE_DOMAIN_RESPONSE)

    _write_centerline(raw_dir / "centerline.geojson")
    _write_fc(
        raw_dir / "side_trails.geojson",
        [
            _line_feature(NEAR_COORDS, {"GlobalID": "side-1", "Name": "Blue Spur", "Blaze": "1"}, feature_id=1),
            _line_feature(NEAR_COORDS, {"GlobalID": "side-2", "Name": "Red Spur", "Blaze": "3"}, feature_id=2),
            _line_feature(NEAR_COORDS, {"GlobalID": "side-3", "Name": "Unblazed Spur", "Blaze": "0"}, feature_id=3),
        ],
    )

    export_trails.main()

    fc = json.loads((out_dir / "trails.geojson").read_text())
    by_name = {f["properties"]["name"]: f["properties"]["blaze_color"] for f in fc["features"]}
    assert by_name["Blue Spur"] == "Blue"
    assert by_name["Red Spur"] == "Red"
    assert by_name["Unblazed Spur"] == "None"  # code 0 is a real decode, not the fallback


def test_export_trails_applies_centerlines_flat_default_with_no_blaze_field(tmp_path, monkeypatch, con):
    # Only the centerline source is registered here - no blaze_field, no
    # network call needed at all, matching sources.json's real shape for it.
    raw_dir, out_dir = _run_export(tmp_path, monkeypatch, [_centerline_source()])
    _write_centerline(raw_dir / "centerline.geojson")

    export_trails.main()

    fc = json.loads((out_dir / "trails.geojson").read_text())
    assert len(fc["features"]) == 1
    props = fc["features"][0]["properties"]
    assert props["source"] == "centerline"
    assert props["blaze_color"] == "White"  # sources.json's flat blaze_default, not hardcoded


def test_export_trails_warns_on_a_feature_that_fails_to_decode(tmp_path, monkeypatch, requests_mock, con, capsys):
    raw_dir, out_dir = _run_export(tmp_path, monkeypatch, [_centerline_source(), _side_trails_source()])
    requests_mock.get(LAYER_URL, json=BLAZE_DOMAIN_RESPONSE)

    _write_centerline(raw_dir / "centerline.geojson")
    _write_fc(
        raw_dir / "side_trails.geojson",
        [
            # Regression fixture for the real gotcha named in
            # features/TRAIL_BLAZE_COLORS.md: side_trails' real Blaze field
            # has features with the literal string "Gold", which is not an
            # actual code in the 0-9 domain.
            _line_feature(NEAR_COORDS, {"GlobalID": "side-gold", "Name": "Gold Spur", "Blaze": "Gold"}, feature_id=1),
        ],
    )

    export_trails.main()

    fc = json.loads((out_dir / "trails.geojson").read_text())
    by_name = {f["properties"]["name"]: f["properties"] for f in fc["features"]}
    assert by_name["Gold Spur"]["blaze_color"] == "Unknown"  # falls back, doesn't crash and isn't silently wrong

    captured = capsys.readouterr()
    assert "WARNING" in captured.out
    assert "side_trails" in captured.out
    assert "side-gold" in captured.out


def test_export_trails_writes_a_sha256_hash_for_the_trails_artifact(tmp_path, monkeypatch, con):
    raw_dir, out_dir = _run_export(tmp_path, monkeypatch, [_centerline_source()])
    _write_centerline(raw_dir / "centerline.geojson")

    manifest = export_trails.main()

    for artifact_kind, filename in (("geojson", "trails.geojson"), ("fgb", "trails.fgb")):
        entry = manifest[artifact_kind]
        on_disk = (out_dir / filename).read_bytes()
        assert entry["sha256"] == hashlib.sha256(on_disk).hexdigest()
        assert len(entry["sha256"]) == 64

    manifest_path = out_dir / "trails_manifest.json"
    assert manifest_path.exists()
    on_disk_manifest = json.loads(manifest_path.read_text())
    assert on_disk_manifest["geojson"]["sha256"] == manifest["geojson"]["sha256"]


def test_export_trails_keeps_a_multilinestring_feature_instead_of_silently_dropping_it(tmp_path, monkeypatch, con):
    """Regression test for a real data gotcha found via manual verification
    against the actual centerline.geojson (2026-07-28): 2 of 3,025 real
    centerline features are MultiLineString, not LineString (e.g. the real
    "Appalachian National Scenic Trail" segments). A naive
    "geometry.type != LineString" filter would silently drop real trail
    mileage from the map - a safety-relevant gap - so MultiLineString must
    be preserved, not skipped."""
    raw_dir, out_dir = _run_export(tmp_path, monkeypatch, [_centerline_source()])
    _write_fc(
        raw_dir / "centerline.geojson",
        [
            _line_feature(CENTERLINE_COORDS, {"GlobalID": "centerline-1", "Name": "Main"}),
            {
                "type": "Feature",
                "id": 2,
                "properties": {"GlobalID": "centerline-multi", "Name": "Split Segment"},
                "geometry": {
                    "type": "MultiLineString",
                    "coordinates": [
                        [[lon, lat] for lon, lat in NEAR_COORDS],
                        [[lon, lat] for lon, lat in [(-73.93, 41.02), (-73.92, 41.03)]],
                    ],
                },
            },
        ],
    )

    export_trails.main()

    fc = json.loads((out_dir / "trails.geojson").read_text())
    # Three disconnected pieces reach the artifact as three chains: the plain
    # segment plus BOTH parts of the MultiLineString. Its name does not
    # survive the chain merge (#161 - two named constituents, no honest
    # single name), so the not-silently-dropped claim is asserted on the
    # geometry itself, which is the thing whose loss #160 was.
    assert len(fc["features"]) == 3


def test_export_trails_warns_and_skips_a_feature_with_missing_geometry(tmp_path, monkeypatch, con, capsys):
    """Regression test for a real data gotcha found via manual verification
    against the actual side_trails.geojson (2026-07-28): one real feature
    ("Alec Kennedy Tent Pad Spur Trail #s 2 & 3") has null geometry entirely.
    There's nothing to draw, but that must produce a loud warning naming the
    feature - never a silent drop, per this project's established
    convention (fetch_topo_quads.py's corrupted-quad warnings)."""
    raw_dir, out_dir = _run_export(tmp_path, monkeypatch, [_centerline_source()])
    _write_fc(
        raw_dir / "centerline.geojson",
        [
            _line_feature(CENTERLINE_COORDS, {"GlobalID": "centerline-1", "Name": "Main"}),
            {
                "type": "Feature",
                "id": 2,
                "properties": {"GlobalID": "centerline-null-geom", "Name": "Ghost Segment"},
                "geometry": None,
            },
        ],
    )

    export_trails.main()

    fc = json.loads((out_dir / "trails.geojson").read_text())
    names = {f["properties"]["name"] for f in fc["features"]}
    assert "Ghost Segment" not in names
    assert "Main" in names  # the rest of the export still succeeds

    captured = capsys.readouterr()
    assert "WARNING" in captured.out
    assert "centerline-null-geom" in captured.out


def test_export_trails_clips_a_line_feature_outside_the_corridor(tmp_path, monkeypatch, requests_mock, con):
    raw_dir, out_dir = _run_export(tmp_path, monkeypatch, [_centerline_source(), _side_trails_source()])
    requests_mock.get(LAYER_URL, json=BLAZE_DOMAIN_RESPONSE)

    _write_centerline(raw_dir / "centerline.geojson")
    _write_fc(
        raw_dir / "side_trails.geojson",
        [
            _line_feature(NEAR_COORDS, {"GlobalID": "side-near", "Name": "Near Spur", "Blaze": "1"}, feature_id=1),
            _line_feature(FAR_COORDS, {"GlobalID": "side-far", "Name": "Far Spur", "Blaze": "1"}, feature_id=2),
        ],
    )

    export_trails.main()

    fc = json.loads((out_dir / "trails.geojson").read_text())
    names = {f["properties"]["name"] for f in fc["features"] if f["properties"]["source"] == "side_trails"}
    assert "Near Spur" in names
    assert "Far Spur" not in names


def test_export_trails_exits_nonzero_when_a_source_returns_zero_features(tmp_path, monkeypatch, requests_mock, con, capsys):
    """Regression test for the missing completeness gate: main() already
    printed each source's feature count ("N line features normalized") but
    never checked it, so a source silently returning 0 features (e.g. an
    ArcGIS schema change) would print 0 and still exit 0. Neither centerline
    nor side_trails is intentionally allowed to be empty (unlike
    export_poi.py's `crossing` poi_type), so this must fail loudly - a
    machine-checkable exit code, not just a log line - and must do so before
    any output, including the manifest, gets written."""
    raw_dir, out_dir = _run_export(tmp_path, monkeypatch, [_centerline_source(), _side_trails_source()])
    requests_mock.get(LAYER_URL, json=BLAZE_DOMAIN_RESPONSE)

    _write_centerline(raw_dir / "centerline.geojson")
    _write_fc(raw_dir / "side_trails.geojson", [])  # e.g. an upstream schema change

    with pytest.raises(SystemExit) as exc_info:
        export_trails.main()

    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "side_trails: 0, expected >= 1" in captured.out
    assert not (out_dir / "trails_manifest.json").exists()  # failed before the manifest was written


def test_export_trails_falls_back_to_feature_id_when_global_id_is_explicitly_null(tmp_path, monkeypatch, con):
    """Regression test: properties.get("GlobalID", feature.get("id")) only
    falls back when the "GlobalID" key is ABSENT, not when it's present but
    JSON null - dict.get's default only kicks in on a missing key, so a raw
    feature carrying an explicit `"GlobalID": null` would return None
    directly instead of falling back, and two such features would collide
    on the literal output id f"{key}:None". The fix checks the RESULTING
    VALUE (like lib/poi_schema.py's unify_poi()) and must still fall back to
    the feature's own top-level id here."""
    feature = _line_feature(CENTERLINE_COORDS, {"GlobalID": None, "Name": "Null GlobalID Segment"}, feature_id="feat-42")

    # At the record level rather than through the published artifact: the
    # centerline's per-segment ids stop at merge_chain_records now (#161), so
    # the fallback this test pins is observable only before the merge - and
    # it still matters there, because spurs.json joins on the same chain for
    # side_trails.
    records = export_trails.build_trail_records(_centerline_source(), [{**feature, "_blaze_color": "White"}])

    assert records[0]["id"] == "centerline:feat-42"


def test_export_trails_substitutes_a_synthetic_id_and_warns_when_a_feature_has_no_global_id_or_top_level_id(
    tmp_path, monkeypatch, con, capsys
):
    """Regression test: when a feature has neither a usable GlobalID nor a
    top-level GeoJSON id, main() must not crash and must not let two such
    features collide on the same output id (both landing on the literal
    f"{key}:None" would be a real, silent collision) - it substitutes a
    synthetic per-feature id and warns loudly instead, matching this file's
    established convention of warning and carrying on rather than aborting
    the whole run over one bad feature."""
    raw_dir, out_dir = _run_export(tmp_path, monkeypatch, [_centerline_source()])
    _write_fc(
        raw_dir / "centerline.geojson",
        [
            {
                "type": "Feature",
                "properties": {"GlobalID": None, "Name": "First Idless Segment"},
                "geometry": {"type": "LineString", "coordinates": [[lon, lat] for lon, lat in CENTERLINE_COORDS]},
            },
            {
                "type": "Feature",
                "properties": {"GlobalID": None, "Name": "Second Idless Segment"},
                "geometry": {"type": "LineString", "coordinates": [[lon, lat] for lon, lat in NEAR_COORDS]},
            },
        ],
    )

    export_trails.main()

    fc = json.loads((out_dir / "trails.geojson").read_text())
    assert len(fc["features"]) == 2  # neither feature silently dropped
    ids = {f["properties"]["id"] for f in fc["features"]}
    assert len(ids) == 2  # the two synthetic ids don't collide
    assert "centerline:None" not in ids

    captured = capsys.readouterr()
    assert "WARNING" in captured.out
    assert "no GlobalID and no top-level id" in captured.out


def test_export_trails_warning_names_the_fallback_id_when_a_decode_failure_coincides_with_a_null_global_id(
    tmp_path, monkeypatch, requests_mock, con, capsys
):
    """Regression test for the other properties.get("GlobalID",
    feature.get("id")) call site - the undecodable-blaze warning in
    normalize_source_features. An explicit `"GlobalID": null` must still
    fall back to the feature's own top-level id in the warning text, not
    print the literal id "None"."""
    raw_dir, out_dir = _run_export(tmp_path, monkeypatch, [_centerline_source(), _side_trails_source()])
    requests_mock.get(LAYER_URL, json=BLAZE_DOMAIN_RESPONSE)

    _write_centerline(raw_dir / "centerline.geojson")
    _write_fc(
        raw_dir / "side_trails.geojson",
        [_line_feature(NEAR_COORDS, {"GlobalID": None, "Name": "Gold Spur", "Blaze": "Gold"}, feature_id="side-fallback")],
    )

    export_trails.main()

    captured = capsys.readouterr()
    assert "feature 'side-fallback' has an undecodable" in captured.out
    assert "feature None has an undecodable" not in captured.out


# --- Centerline chain merging (#161) ----------------------------------------
#
# geojson-vt's per-zoom simplification drops whole features under a projected
# length bar, and ATC's ~3,000 short centerline segments sat under it at
# corridor zooms - the miles-long gaps of #160. Merging contiguous segments
# into maximal chains puts every published centerline feature far above the
# bar, which is what lets the client return its trails source's `tolerance`
# to the default (lib/trailShape.ts sniffs the chain ids below to know it
# safely can). Spurs are deliberately untouched: each is its own destination
# and its own sheet, and spurs.json joins on their individual ids.


def _chain_record(record_id, coords, *, source="centerline", name=None, blaze="White"):
    wkt = "LINESTRING (" + ", ".join(f"{lon} {lat}" for lon, lat in coords) + ")"
    return {"id": record_id, "source": source, "name": name, "blaze_color": blaze, "wkt": wkt}


def test_touching_centerline_segments_merge_into_one_chain():
    records, stats = export_trails.merge_chain_records(
        [
            _chain_record("centerline:a", [(-74.0, 41.0), (-73.9, 41.1)]),
            _chain_record("centerline:b", [(-73.9, 41.1), (-73.8, 41.2)]),
        ]
    )

    assert [r["id"] for r in records] == ["centerline:chain:0"]
    assert stats == {"centerline": {"constituents": 2, "chains": 1}}


def test_disconnected_pieces_stay_separate_chains_in_a_stable_order():
    """linemerge only joins endpoints that touch exactly - the real data
    merges to 558 pieces, not one - and the chain ids must not depend on
    library ordering: the same input has to publish the same artifact."""
    south = _chain_record("centerline:s", [(-74.0, 40.0), (-74.0, 40.1)])
    north_piece = _chain_record("centerline:n", [(-73.0, 42.0), (-73.0, 42.1)])

    forwards, _ = export_trails.merge_chain_records([south, north_piece])
    backwards, _ = export_trails.merge_chain_records([north_piece, south])

    assert [r["wkt"] for r in forwards] == [r["wkt"] for r in backwards]
    assert [r["id"] for r in forwards] == ["centerline:chain:0", "centerline:chain:1"]


def test_side_trails_are_never_merged():
    """Each spur is its own destination and its own line-detail sheet, and
    spurs.json keys off these exact ids - collapsing them would orphan every
    record in it."""
    spur_a = _chain_record("side_trails:a", [(-74.0, 41.0), (-74.0, 41.001)], source="side_trails", blaze="Blue")
    spur_b = _chain_record("side_trails:b", [(-74.0, 41.001), (-74.0, 41.002)], source="side_trails", blaze="Blue")

    records, stats = export_trails.merge_chain_records([spur_a, spur_b])

    assert [r["id"] for r in records] == ["side_trails:a", "side_trails:b"]
    assert stats == {}


def test_chains_never_cross_a_blaze_boundary():
    """One feature carries one blaze_color, so merging across a boundary
    would repaint real trail. The centerline is uniformly White today; this
    pins the guard for the imported source that is not."""
    white = _chain_record("centerline:w", [(-74.0, 41.0), (-73.9, 41.1)], blaze="White")
    blue = _chain_record("centerline:b", [(-73.9, 41.1), (-73.8, 41.2)], blaze="Blue")

    records, _ = export_trails.merge_chain_records([white, blue])

    assert sorted(r["blaze_color"] for r in records) == ["Blue", "White"]
    assert all(r["id"].startswith("centerline:chain:") for r in records)


def test_a_chain_keeps_the_name_only_when_every_constituent_agreed():
    agreed, _ = export_trails.merge_chain_records(
        [
            _chain_record("centerline:a", [(-74.0, 41.0), (-73.9, 41.1)], name="Appalachian National Scenic Trail"),
            _chain_record("centerline:b", [(-73.9, 41.1), (-73.8, 41.2)], name="Appalachian National Scenic Trail"),
        ]
    )
    disagreed, _ = export_trails.merge_chain_records(
        [
            _chain_record("centerline:a", [(-74.0, 41.0), (-73.9, 41.1)], name="Georgia Section"),
            _chain_record("centerline:b", [(-73.9, 41.1), (-73.8, 41.2)], name="Maine Section"),
        ]
    )

    assert agreed[0]["name"] == "Appalachian National Scenic Trail"
    # Two named stretches have no honest single name - null says so, rather
    # than picking whichever won by list order.
    assert disagreed[0]["name"] is None


def test_the_manifest_records_the_pre_merge_segment_count(tmp_path, monkeypatch, con):
    """check_output_quality.trails_verdict tracks completeness on the
    constituent count, so segments merging into chains does not read as a
    broken export while an upstream actually losing segments still would."""
    raw_dir, out_dir = _run_export(tmp_path, monkeypatch, [_centerline_source()])
    _write_fc(
        raw_dir / "centerline.geojson",
        [
            _line_feature(CENTERLINE_COORDS, {"GlobalID": "c-1", "Name": "A"}, feature_id=1),
            _line_feature([CENTERLINE_COORDS[-1], (-73.8, 41.2)], {"GlobalID": "c-2", "Name": "B"}, feature_id=2),
        ],
    )

    manifest = export_trails.main()

    assert manifest["geojson"]["feature_count"] == 1  # one chain published
    assert manifest["constituent_count"] == 2  # two surveyed segments behind it
    assert manifest["chain_counts"] == {"centerline": 1}
    fc = json.loads((out_dir / "trails.geojson").read_text())
    assert [f["properties"]["id"] for f in fc["features"]] == ["centerline:chain:0"]


@pytest.fixture
def overview_out(tmp_path, monkeypatch):
    """write_overview writes to OUT_DIR, which is the repository's data
    directory unless a test says otherwise - and a test that leaves an
    artifact in it is a test that changes what the next `publish.py` uploads."""
    out_dir = tmp_path / "processed"
    monkeypatch.setattr(export_trails, "OUT_DIR", out_dir)
    return out_dir


# The corridor-view centerline (#869). What matters is not that it is small -
# any simplification is - but that it stays HONEST while being small: the same
# geometry, no further from the surveyed line than the tolerance it declares,
# and never mistaken for the artifact a hiker navigates by.


def test_the_overview_is_one_feature_whatever_the_export_holds(overview_out):
    """Per-feature JSON wrappers, not vertices, are most of a simplified
    centerline: at 250 m the published export's 3,025 wrappers were 466 KB of
    a 525 KB file. One feature drops all of it, and nothing reads this
    artifact per-feature - it is a shape to draw, never a trail to identify."""
    records = [
        {"id": "c-1", "source": "centerline", "name": "A.T.", "blaze_color": "White", "wkt": "LINESTRING (-74 41, -74.1 41.1)"},
        {
            "id": "c-2",
            "source": "centerline",
            "name": "A.T.",
            "blaze_color": "White",
            "wkt": "LINESTRING (-74.2 41.2, -74.3 41.3)",
        },
    ]

    entry = export_trails.write_overview(records)
    body = json.loads(Path(entry["path"]).read_text())

    assert len(body["features"]) == 1
    assert body["features"][0]["geometry"]["type"] == "MultiLineString"
    assert entry["line_count"] == 2


def test_the_overview_carries_only_the_centerline(overview_out):
    """A side trail at the corridor view is sub-pixel and is not what the
    sketch is for - it exists to answer "where does the A.T. run" while the
    real line is still arriving."""
    records = [
        {"id": "c-1", "source": "centerline", "name": "A.T.", "blaze_color": "White", "wkt": "LINESTRING (-74 41, -74.1 41.1)"},
        {"id": "s-1", "source": "side_trails", "name": "Spur", "blaze_color": "Blue", "wkt": "LINESTRING (-74 41, -74.01 41.01)"},
    ]

    entry = export_trails.write_overview(records)
    body = json.loads(Path(entry["path"]).read_text())

    assert entry["line_count"] == 1
    assert body["features"][0]["properties"] == {"source": "centerline", "blaze_color": "White"}


def test_no_overview_vertex_is_further_from_the_surveyed_line_than_it_claims(overview_out):
    """The property the client's `maxzoom` is reasoned from. Douglas-Peucker
    guarantees it; this asserts the guarantee survives the projection either
    side of it, because a tolerance applied in degrees would mean two
    different distances depending on direction (simplify_records' block)."""
    surveyed = LineString([(-74 + i * 0.002, 41 + math.sin(i / 3) * 0.004) for i in range(400)])
    records = [{"id": "c-1", "source": "centerline", "name": "A.T.", "blaze_color": "White", "wkt": surveyed.wkt}]

    entry = export_trails.write_overview(records)
    body = json.loads(Path(entry["path"]).read_text())
    drawn = shape(body["features"][0]["geometry"])

    # In metres, the same projection the simplification used.
    projected_surveyed = shapely_transform(export_trails._TO_METRIC, surveyed)
    projected_drawn = shapely_transform(export_trails._TO_METRIC, drawn)
    # Rounding the coordinates to four decimals moves a point by at most
    # ~11 m of longitude at these latitudes, so the bar is the tolerance plus
    # that - not the tolerance alone, which would be a test asserting an
    # arithmetic it does not perform.
    assert projected_drawn.hausdorff_distance(projected_surveyed) < (export_trails.OVERVIEW_SIMPLIFY_TOLERANCE_M + 20)


def test_the_overview_keeps_the_ends_of_the_trail(overview_out):
    """The two vertices a hiker could notice missing: Springer and Katahdin.
    Douglas-Peucker preserves endpoints, and a sketch that quietly stopped
    short of either end would be a false statement about where the trail
    goes."""
    surveyed = LineString([(-74 + i * 0.01, 41 + i * 0.01) for i in range(50)])
    records = [{"id": "c-1", "source": "centerline", "name": "A.T.", "blaze_color": "White", "wkt": surveyed.wkt}]

    entry = export_trails.write_overview(records)
    line = json.loads(Path(entry["path"]).read_text())["features"][0]["geometry"]["coordinates"][0]

    decimals = export_trails.OVERVIEW_COORDINATE_DECIMALS
    assert line[0] == [round(surveyed.coords[0][0], decimals), round(surveyed.coords[0][1], decimals)]
    assert line[-1] == [round(surveyed.coords[-1][0], decimals), round(surveyed.coords[-1][1], decimals)]


def test_the_export_publishes_the_overview_beside_the_full_line(tmp_path, monkeypatch, con):
    """Both artifacts, from one run, with the overview's own manifest entry -
    which is what publish.py turns into the flat `trails_overview.geojson`
    key the client fetches."""
    raw_dir, out_dir = _run_export(tmp_path, monkeypatch, [_centerline_source()])
    _write_centerline(raw_dir / "centerline.geojson")

    manifest = export_trails.main()

    assert (out_dir / "trails.geojson").exists()
    assert (out_dir / "trails_overview.geojson").exists()
    assert manifest["overview"]["sha256"] == hashlib.sha256((out_dir / "trails_overview.geojson").read_bytes()).hexdigest()
    assert manifest["overview"]["tolerance_m"] == export_trails.OVERVIEW_SIMPLIFY_TOLERANCE_M


def test_the_overview_is_a_fraction_of_the_line_it_sketches(tmp_path, monkeypatch, con):
    """The whole reason it exists. Measured against the live export it is 81x
    smaller (4,143,296 gzipped bytes against 51,068, 2026-08-20); this
    fixture is far too small for that ratio, so what is asserted here is the
    direction and not the figure."""
    raw_dir, out_dir = _run_export(tmp_path, monkeypatch, [_centerline_source()])
    _write_fc(
        raw_dir / "centerline.geojson",
        [_line_feature([(-74 + i * 0.001, 41 + math.sin(i / 5) * 0.002) for i in range(800)], {"GlobalID": "c-1"})],
    )

    export_trails.main()

    assert (out_dir / "trails_overview.geojson").stat().st_size < (out_dir / "trails.geojson").stat().st_size
