"""Tests for export_nearby_trails.py - the trail lines other organizations
maintain (#950, features/NEARBY_TRAILS.md).

Small synthetic fixtures throughout, never the real 16,641-feature OPRHP
layer and never a live network call (TESTING.md). Where a test's number comes
from the real data it is stated as a comment and the fixture reproduces the
SHAPE of it, not the volume - the point of a fixture here is that a reviewer
can see the whole input on one screen.

The asymmetry this suite is written around, and it is the same one
wrongWay.test.ts states for its own module: for a map that draws somebody
else's trails, DROPPING A REAL TRAIL IS THE EXPENSIVE FAILURE and drawing one
line twice is the cheap one. A hiker who cannot see the trail they are
standing on is worse off than one who sees a duplicate they can walk either
way. Several tests below exist only to pin that direction.
"""

import json

import pytest
from shapely.geometry import shape

import export_nearby_trails as ex

# Inside NYC_SOURCE_SURVEY.md §1's ring (Harriman-ish), and far enough from
# any real data that nothing here can be confused for a measurement.
IN_RING = [(-74.1, 41.25), (-74.09, 41.26)]
# North of the ring's 42.55 cut - the Long Path's Albany end, in miniature.
NORTH_OF_RING = [(-74.0, 43.1), (-73.99, 43.11)]
# East of the ring's -73.4 edge.
OUTSIDE_RING = [(-72.0, 41.2), (-71.99, 41.21)]


def _feature(coords, properties, feature_id=1):
    return {
        "type": "Feature",
        "id": feature_id,
        "geometry": {"type": "LineString", "coordinates": [[lon, lat] for lon, lat in coords]},
        "properties": properties,
    }


def _oprhp_source(**overrides):
    """The shape of the real oprhp_trails entry, minus the prose."""
    source = {
        "key": "oprhp_trails",
        "title": "NYS Parks Trails",
        "kind": "external_arcgis_layer",
        "url": "https://example.test/oprhp",
        "steward": "New York State Office of Parks, Recreation and Historic Preservation",
        "attribution": "NYS OPRHP",
        "blaze_field": "Blaze",
        "name_field": "Name",
        "foot_field": "Foot",
        "status_field": "Status",
        "unit_field": "Unit",
        "reaches_hikers": False,
    }
    source.update(overrides)
    return source


def _oprhp_properties(**overrides):
    properties = {"Name": "Ramapo-Dunderberg", "Blaze": "Red", "Foot": "Y", "Status": "Open", "Unit": "Palisades"}
    properties.update(overrides)
    return properties


def _run(tmp_path, monkeypatch, sources, features_by_key, mapping=None):
    raw_dir = tmp_path / "external"
    raw_dir.mkdir()
    out_dir = tmp_path / "processed"
    sources_path = tmp_path / "sources.json"
    sources_path.write_text(json.dumps({"_comment": "test fixture", "sources": sources}))

    for key, features in features_by_key.items():
        (raw_dir / f"{key}.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": features}))

    monkeypatch.setattr(ex, "RAW_DIR", raw_dir)
    monkeypatch.setattr(ex, "OUT_DIR", out_dir)
    monkeypatch.setattr(ex, "SOURCES_PATH", sources_path)
    monkeypatch.setattr(ex, "load_blaze_mapping", lambda: mapping or {})

    manifest = ex.main()
    body = json.loads((out_dir / ex.ARTIFACT_NAME).read_text())
    return manifest, body


# --------------------------------------------------------------------------
# The properties the client reads. These names are a contract with
# client/src/map/style.ts, nearbyTrails.ts, trailLabels.ts and
# lib/closureStyle.ts - see the module docstring.
# --------------------------------------------------------------------------


def test_publishes_the_five_properties_the_client_draws_from(tmp_path, monkeypatch):
    _, body = _run(
        tmp_path,
        monkeypatch,
        [_oprhp_source()],
        {"oprhp_trails": [_feature(IN_RING, _oprhp_properties())]},
        mapping={"oprhp_trails": {"mapped": {"Red": "Red"}}},
    )

    (feature,) = body["features"]
    assert feature["properties"] == {
        "id": "oprhp_trails:1",
        "source": "oprhp_trails",
        "name": "Ramapo-Dunderberg",
        "blaze_color": "Red",
        "trail_status": "open",
    }


def test_the_source_key_is_the_registry_key_so_the_client_ghosts_it(tmp_path, monkeypatch):
    # map/nearbyTrails.ts ghosts every `source` outside CHOSEN_SYSTEM_SOURCES
    # (['centerline', 'side_trails']). Nothing in this export is in that list,
    # and nothing here should ever write one of those two keys - that would
    # promote another organization's line to the chosen trail's own tier.
    _, body = _run(
        tmp_path,
        monkeypatch,
        [_oprhp_source()],
        {"oprhp_trails": [_feature(IN_RING, _oprhp_properties())]},
    )

    sources = {f["properties"]["source"] for f in body["features"]}
    assert sources == {"oprhp_trails"}
    assert not sources & {"centerline", "side_trails"}


# --------------------------------------------------------------------------
# Filter 3: status.
# --------------------------------------------------------------------------


def test_a_long_term_closed_trail_ships_carrying_the_status_the_closure_band_reads(tmp_path, monkeypatch):
    # features/NEARBY_TRAILS.md §3: `Closed` SHIPS, drawn with the closure
    # treatment, so somebody at the trailhead with an old paper map is told
    # rather than the trail silently missing. lib/closureStyle.ts compares
    # this value downcased against "closed".
    _, body = _run(
        tmp_path,
        monkeypatch,
        [_oprhp_source()],
        {"oprhp_trails": [_feature(IN_RING, _oprhp_properties(Status="Closed"))]},
        mapping={"oprhp_trails": {"mapped": {"Red": "Red"}}},
    )

    (feature,) = body["features"]
    assert feature["properties"]["trail_status"] == "closed"


@pytest.mark.parametrize("status", ["Proposed", "Unknown", None, "", "Something OPRHP has not published before"])
def test_a_status_that_is_not_open_or_closed_is_dropped_rather_than_assumed_walkable(tmp_path, monkeypatch, status):
    # Omit rather than guess. A `Proposed` trail is not ground; an unknown
    # status drawn as walkable is a guess; and an unrecognised NEW value has
    # to take the same path, because the failure of drawing a closed trail as
    # open is a hiker walking into it.
    manifest, body = _run(
        tmp_path,
        monkeypatch,
        [_oprhp_source()],
        {
            "oprhp_trails": [
                _feature(IN_RING, _oprhp_properties(Status="Open"), feature_id=1),
                _feature(IN_RING, _oprhp_properties(Name="Not ground", Status=status), feature_id=2),
            ]
        },
        mapping={"oprhp_trails": {"mapped": {"Red": "Red"}}},
    )

    assert [f["properties"]["id"] for f in body["features"]] == ["oprhp_trails:1"]
    assert sum(manifest["sources"]["oprhp_trails"]["dropped"].values()) == 1


def _no_status_source(**overrides):
    """NYNJTC's shape: a name and a blaze, no use flags and no status."""
    source = {
        "key": "nynjtc_long_path",
        "title": "NYNJTC Long Path",
        "kind": "external_arcgis_layer",
        "url": "https://example.test/lp",
        "steward": "New York-New Jersey Trail Conference",
        "attribution": "NYNJTC",
        "blaze_field": "Blaze",
        "name_field": "Trail_Name",
        "owns_route_names": ["Long Path"],
        "reaches_hikers": False,
    }
    source.update(overrides)
    return source


def test_a_source_with_no_status_column_ships_open_rather_than_inventing_a_closure(tmp_path, monkeypatch):
    # NYNJTC's extracts have no status field. A layer that cannot say "closed"
    # must never be read as saying it - that is the closure treatment's whole
    # credibility, and a false barred band is the cry-wolf failure.
    _, body = _run(
        tmp_path,
        monkeypatch,
        [_no_status_source()],
        {"nynjtc_long_path": [_feature(IN_RING, {"Trail_Name": "Long Path", "Blaze": "aqua"})]},
        mapping={"nynjtc_long_path": {"mapped": {"aqua": "Aqua"}}},
    )

    (feature,) = body["features"]
    assert feature["properties"]["trail_status"] == "open"


# --------------------------------------------------------------------------
# Filter 1: hiking only.
# --------------------------------------------------------------------------


def test_a_segment_that_does_not_allow_foot_travel_is_dropped(tmp_path, monkeypatch):
    # The maintainer's 2026-08-18 decision: "It's OurHike, not OurBike".
    manifest, body = _run(
        tmp_path,
        monkeypatch,
        [_oprhp_source()],
        {
            "oprhp_trails": [
                _feature(IN_RING, _oprhp_properties(), feature_id=1),
                _feature(IN_RING, _oprhp_properties(Name="Horn Hill Bike Trail", Foot="N"), feature_id=2),
            ]
        },
        mapping={"oprhp_trails": {"mapped": {"Red": "Red"}}},
    )

    assert [f["properties"]["id"] for f in body["features"]] == ["oprhp_trails:1"]
    assert manifest["sources"]["oprhp_trails"]["dropped"] == {"not a foot trail: Foot='N'": 1}


def test_a_source_declaring_no_foot_field_keeps_every_row(tmp_path, monkeypatch):
    # NYNJTC publishes hiking trails and nothing else, so there are no use
    # flags to read. Absent must not mean excluded, or registering a source
    # that is entirely hiking trails would export nothing.
    _, body = _run(
        tmp_path,
        monkeypatch,
        [_no_status_source()],
        {"nynjtc_long_path": [_feature(IN_RING, {"Trail_Name": "Long Path", "Blaze": "aqua"})]},
        mapping={"nynjtc_long_path": {"mapped": {"aqua": "Aqua"}}},
    )

    assert len(body["features"]) == 1


# --------------------------------------------------------------------------
# Filter 2: the ring.
# --------------------------------------------------------------------------


def test_a_trail_outside_the_ring_is_dropped_and_one_crossing_its_edge_is_kept_whole(tmp_path, monkeypatch):
    # Kept if it INTERSECTS, and never cut at the boundary - export_trails.py's
    # own corridor rule. Cutting would end a trail at a line nobody drew on
    # the ground.
    crossing = [(-73.5, 41.2), (-73.2, 41.2)]  # starts inside, ends east of -73.4
    manifest, body = _run(
        tmp_path,
        monkeypatch,
        [_oprhp_source()],
        {
            "oprhp_trails": [
                _feature(crossing, _oprhp_properties(Name="Crosses the edge"), feature_id=1),
                _feature(OUTSIDE_RING, _oprhp_properties(Name="Wholly outside"), feature_id=2),
                _feature(NORTH_OF_RING, _oprhp_properties(Name="North of the cut"), feature_id=3),
            ]
        },
        mapping={"oprhp_trails": {"mapped": {"Red": "Red"}}},
    )

    assert [f["properties"]["name"] for f in body["features"]] == ["Crosses the edge"]
    assert manifest["sources"]["oprhp_trails"]["dropped"] == {"outside the ring": 2}
    # Whole, not truncated at -73.4: both original endpoints survive.
    kept = shape(body["features"][0]["geometry"])
    assert kept.bounds[2] == pytest.approx(-73.2)


def test_long_island_is_excluded_by_the_stewards_own_region_name(tmp_path, monkeypatch):
    # NYC_SOURCE_SURVEY.md §1(a)'s open edge, resolved toward the survey's
    # county list. Measured 2026-08-24 against the live layer: 1,951 of the
    # 5,759 segments that pass every other filter are `Unit: Long Island`.
    manifest, body = _run(
        tmp_path,
        monkeypatch,
        [_oprhp_source()],
        {
            "oprhp_trails": [
                _feature(IN_RING, _oprhp_properties(Unit="Palisades"), feature_id=1),
                _feature(IN_RING, _oprhp_properties(Name="Some LI path", Unit="Long Island"), feature_id=2),
                _feature(IN_RING, _oprhp_properties(Name="A city park path", Unit="New York City"), feature_id=3),
            ]
        },
        mapping={"oprhp_trails": {"mapped": {"Red": "Red"}}},
    )

    # New York City stays: §1 leaves Long Island open and says nothing about
    # the close-in parks a subway rider reaches.
    assert [f["properties"]["id"] for f in body["features"]] == ["oprhp_trails:1", "oprhp_trails:3"]
    assert manifest["sources"]["oprhp_trails"]["dropped"] == {"excluded unit: Long Island": 1}


# --------------------------------------------------------------------------
# Filter 4: the route owner's line wins. The expensive-failure tests.
# --------------------------------------------------------------------------


def test_the_landowners_copy_of_a_route_another_org_owns_is_suppressed(tmp_path, monkeypatch):
    manifest, body = _run(
        tmp_path,
        monkeypatch,
        [_at_owner_source(), _oprhp_source()],
        {
            "oprhp_trails": [
                _feature(IN_RING, _oprhp_properties(Name="Appalachian Trail", Blaze="White"), feature_id=1),
                _feature(IN_RING, _oprhp_properties(Name="Timp-Torne"), feature_id=2),
            ]
        },
        mapping={"oprhp_trails": {"mapped": {"White": "White", "Red": "Red"}}},
    )

    assert [f["properties"]["name"] for f in body["features"]] == ["Timp-Torne"]
    assert manifest["sources"]["oprhp_trails"]["dropped"] == {"route owned by centerline": 1}


def _at_owner_source():
    """ATC's centerline, as the registry declares it: the owner of the A.T.'s
    route, and not itself part of this export (no external kind)."""
    return {
        "key": "centerline",
        "url": "https://example.test/at",
        "blaze_default": "White",
        "owns_route_names": ["Appalachian Trail"],
    }


def test_a_source_never_suppresses_its_own_route(tmp_path, monkeypatch):
    # nynjtc_long_path owns "Long Path". If ownership were read as "this name
    # is spoken for", NYNJTC's own Long Path would delete itself and the
    # route would vanish from the map entirely.
    _, body = _run(
        tmp_path,
        monkeypatch,
        [_no_status_source()],
        {"nynjtc_long_path": [_feature(IN_RING, {"Trail_Name": "Long Path", "Blaze": "aqua"})]},
        mapping={"nynjtc_long_path": {"mapped": {"aqua": "Aqua"}}},
    )

    assert [f["properties"]["name"] for f in body["features"]] == ["Long Path"]


def test_a_distinct_trail_the_owned_route_runs_along_is_kept(tmp_path, monkeypatch):
    """The expensive failure this filter is most likely to cause.

    Measured on the live layer 2026-08-24: 26 OPRHP segments read
    `Alt_Name: Appalachian Trail` while their own `Name` is something else -
    the 1777 East Trail (19), the Ramapo-Dunderberg (3), the Arden Surebridge,
    the Timp-Torne. Those are real trails the A.T. runs along for a stretch.
    Matching an alternate name would delete every one of them.
    """
    manifest, body = _run(
        tmp_path,
        monkeypatch,
        [_at_owner_source(), _oprhp_source()],
        {"oprhp_trails": [_feature(IN_RING, _oprhp_properties(Name="1777 East Trail", Alt_Name="Appalachian Trail"))]},
        mapping={"oprhp_trails": {"mapped": {"Red": "Red"}}},
    )

    assert [f["properties"]["name"] for f in body["features"]] == ["1777 East Trail"]
    assert manifest["sources"]["oprhp_trails"]["dropped"] == {}


def test_a_name_that_merely_starts_with_an_owned_route_is_kept(tmp_path, monkeypatch):
    # "Appalachian Trail Connector" (6 segments live) and "Appalachian Trail
    # Bypass" (2) are their own trails. An owned-name test that matched on
    # prefix rather than equality would take both.
    _, body = _run(
        tmp_path,
        monkeypatch,
        [_at_owner_source(), _oprhp_source()],
        {
            "oprhp_trails": [
                _feature(IN_RING, _oprhp_properties(Name="Appalachian Trail Connector"), feature_id=1),
                _feature(IN_RING, _oprhp_properties(Name="Appalachian Trail Bypass"), feature_id=2),
            ]
        },
        mapping={"oprhp_trails": {"mapped": {"Red": "Red"}}},
    )

    assert len(body["features"]) == 2


# --------------------------------------------------------------------------
# Blazes.
# --------------------------------------------------------------------------


def test_a_source_that_states_no_blaze_for_a_row_is_counted_not_warned_per_feature(tmp_path, monkeypatch, capsys):
    # 2,036 of the 3,618 OPRHP rows this export keeps have a null Blaze
    # (measured 2026-08-24). A warning each would bury the handful that are
    # genuinely unreviewed values.
    manifest, body = _run(
        tmp_path,
        monkeypatch,
        [_oprhp_source()],
        {
            "oprhp_trails": [
                _feature(IN_RING, _oprhp_properties(Blaze=None), feature_id=1),
                _feature(IN_RING, _oprhp_properties(Blaze="   "), feature_id=2),
            ]
        },
    )

    assert [f["properties"]["blaze_color"] for f in body["features"]] == ["Unknown", "Unknown"]
    assert manifest["sources"]["oprhp_trails"]["blazes"] == {"absent": 2}
    assert "WARNING" not in capsys.readouterr().out


def test_a_value_nobody_has_reviewed_warns_loudly_per_feature(tmp_path, monkeypatch, capsys):
    # The distinction the counted case above exists to protect: a value the
    # reviewed table has never heard of is a gap in OUR file, and it gets a
    # line naming the feature so somebody can go and look at it.
    _, body = _run(
        tmp_path,
        monkeypatch,
        [_oprhp_source()],
        {"oprhp_trails": [_feature(IN_RING, _oprhp_properties(Blaze="Chartreuse"))]},
        mapping={"oprhp_trails": {"mapped": {"Red": "Red"}}},
    )

    out = capsys.readouterr().out
    assert "WARNING" in out and "Chartreuse" in out and "oprhp_trails feature 1" in out
    assert body["features"][0]["properties"]["blaze_color"] == "Unknown"


def test_a_deferred_value_renders_neutral_without_a_warning(tmp_path, monkeypatch, capsys):
    # A deferred value is a decision already recorded in
    # reference/blaze_mapping.json, not an oversight - repeating it per
    # feature is noise.
    _, body = _run(
        tmp_path,
        monkeypatch,
        [_oprhp_source()],
        {"oprhp_trails": [_feature(IN_RING, _oprhp_properties(Blaze="Pink"))]},
        mapping={"oprhp_trails": {"mapped": {"Red": "Red"}, "deferred": {"Pink": {"count": 171}}}},
    )

    assert body["features"][0]["properties"]["blaze_color"] == "Unknown"
    assert "WARNING" not in capsys.readouterr().out


def test_a_source_with_no_blaze_field_takes_its_declared_default(tmp_path, monkeypatch, capsys):
    # nynjtc_highlands_trail publishes no blaze at all and declares the
    # neutral. That is the absence stated, not a paint guessed, and it must
    # not warn - there is nothing for anybody to review.
    manifest, body = _run(
        tmp_path,
        monkeypatch,
        [
            {
                "key": "nynjtc_highlands_trail",
                "url": "https://example.test/ht",
                "kind": "external_arcgis_layer",
                "blaze_default": "Unknown",
                "name_field": "Trail_Name",
                "reaches_hikers": False,
            }
        ],
        {"nynjtc_highlands_trail": [_feature(IN_RING, {"Trail_Name": "Highlands"})]},
    )

    assert body["features"][0]["properties"]["blaze_color"] == "Unknown"
    assert manifest["sources"]["nynjtc_highlands_trail"]["blazes"] == {"default": 1}
    assert "WARNING" not in capsys.readouterr().out


# --------------------------------------------------------------------------
# Selection, completeness and the manifest.
# --------------------------------------------------------------------------


def test_only_external_line_sources_are_exported(tmp_path, monkeypatch):
    registry = {
        "sources": [
            # An A.T. line source: blaze metadata, but not an external layer.
            {"key": "centerline", "blaze_default": "White"},
            # An external layer that is not lines - no blaze metadata.
            {"key": "oprhp_park_polygons", "kind": "external_arcgis_layer"},
            _oprhp_source(),
        ]
    }
    assert [s["key"] for s in ex.network_line_sources(registry)] == ["oprhp_trails"]


def test_a_source_that_returns_nothing_fails_the_run_rather_than_shrinking_the_map(tmp_path, monkeypatch):
    # export_trails.py's completeness gate, for the same reason: an ArcGIS
    # schema change that renames `Status` would otherwise drop every feature
    # and exit 0.
    with pytest.raises(SystemExit):
        _run(
            tmp_path,
            monkeypatch,
            [_oprhp_source()],
            {"oprhp_trails": [_feature(IN_RING, _oprhp_properties(Status="Proposed"))]},
        )


def test_a_source_whose_every_feature_is_suppressed_also_fails_the_run(tmp_path, monkeypatch):
    """Suppression counts toward the completeness gate, deliberately.

    A registered source contributing nothing is the same event whether the
    cause is a renamed status column or a route-owner rule that swallowed the
    whole layer, and both want a human to look. The alternative - exempting
    suppression - would let a mis-typed `owns_route_names` silently empty a
    source, which is the failure this export can least afford.
    """
    with pytest.raises(SystemExit):
        _run(
            tmp_path,
            monkeypatch,
            [_at_owner_source(), _oprhp_source()],
            {"oprhp_trails": [_feature(IN_RING, _oprhp_properties(Name="Appalachian Trail", Blaze="White"))]},
            mapping={"oprhp_trails": {"mapped": {"White": "White"}}},
        )


def test_a_missing_raw_file_names_the_fetcher_that_writes_it(tmp_path, monkeypatch):
    raw_dir = tmp_path / "external"
    raw_dir.mkdir()
    sources_path = tmp_path / "sources.json"
    sources_path.write_text(json.dumps({"sources": [_oprhp_source()]}))
    monkeypatch.setattr(ex, "RAW_DIR", raw_dir)
    monkeypatch.setattr(ex, "OUT_DIR", tmp_path / "processed")
    monkeypatch.setattr(ex, "SOURCES_PATH", sources_path)

    with pytest.raises(FileNotFoundError, match="fetch_external_layers.py"):
        ex.main()


def test_the_manifest_carries_each_sources_steward_and_whether_it_ships(tmp_path, monkeypatch):
    # features/NEARBY_TRAILS.md §6's provenance line needs one place to read a
    # steward from, and publish.py needs to know these are held back.
    manifest, _ = _run(
        tmp_path,
        monkeypatch,
        [_oprhp_source()],
        {"oprhp_trails": [_feature(IN_RING, _oprhp_properties())]},
        mapping={"oprhp_trails": {"mapped": {"Red": "Red"}}},
    )

    entry = manifest["sources"]["oprhp_trails"]
    assert entry["steward"] == "New York State Office of Parks, Recreation and Historic Preservation"
    assert entry["attribution"] == "NYS OPRHP"
    assert entry["reaches_hikers"] is False
    assert manifest["feature_count"] == 1
    assert manifest["ring_bbox"] == list(ex.RING_BBOX)
    assert len(manifest["sha256"]) == 64
