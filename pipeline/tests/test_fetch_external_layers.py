"""HTTP-mocked tests for fetch_external_layers.py - fetch_all.py's harness
pointed at the external-organization loop, plus the one rule that is new
here: `may_be_empty` lets a temporary-closures layer come back with zero
features as a fact rather than a failure, and lets nothing else."""

import json

import pytest

import fetch_external_layers

LAYER_URL = "https://services.arcgis.com/fakeorg/arcgis/rest/services/Fake/FeatureServer/0"


def _setup(tmp_path, monkeypatch, sources, prior_manifest=None):
    (tmp_path / "sources.json").write_text(json.dumps({"sources": sources}))
    raw_dir = tmp_path / "data" / "raw" / "external"
    raw_dir.mkdir(parents=True)
    manifest_path = raw_dir / "manifest.json"
    if prior_manifest is not None:
        manifest_path.write_text(json.dumps(prior_manifest))

    monkeypatch.setattr(fetch_external_layers, "SOURCES_PATH", tmp_path / "sources.json")
    monkeypatch.setattr(fetch_external_layers, "RAW_DIR", raw_dir)
    monkeypatch.setattr(fetch_external_layers, "MANIFEST_PATH", manifest_path)
    return raw_dir, manifest_path


def _external(key="oprhp_fake", **extra):
    return {"key": key, "title": "Fake External Layer", "kind": "external_arcgis_layer", "url": LAYER_URL, **extra}


def test_unchanged_source_is_skipped_not_refetched(tmp_path, monkeypatch, requests_mock):
    raw_dir, manifest_path = _setup(
        tmp_path,
        monkeypatch,
        sources=[_external()],
        prior_manifest={
            "oprhp_fake": {"title": "Fake External Layer", "url": LAYER_URL, "feature_count": 1, "data_last_edit_date": 123}
        },
    )
    (raw_dir / "oprhp_fake.geojson").write_text('{"type": "FeatureCollection", "features": []}')

    requests_mock.get(LAYER_URL, json={"editingInfo": {"dataLastEditDate": 123}})
    # Deliberately no mock for LAYER_URL + "/query" - a fetch attempt raises
    # NoMockAddress and fails loudly, exactly test_fetch_all.py's guarantee.

    fetch_external_layers.main()

    manifest = json.loads(manifest_path.read_text())
    assert manifest["oprhp_fake"]["data_last_edit_date"] == 123


def test_changed_source_is_refetched(tmp_path, monkeypatch, requests_mock):
    raw_dir, manifest_path = _setup(
        tmp_path,
        monkeypatch,
        sources=[_external()],
        prior_manifest={
            "oprhp_fake": {"title": "Fake External Layer", "url": LAYER_URL, "feature_count": 1, "data_last_edit_date": 111}
        },
    )
    (raw_dir / "oprhp_fake.geojson").write_text('{"type": "FeatureCollection", "features": []}')

    requests_mock.get(LAYER_URL, json={"editingInfo": {"dataLastEditDate": 999}})
    # Two pages: a short-but-nonempty page followed by the empty page that
    # ends pagination (see test_lib_arcgis.py) - a single fixed non-empty
    # response would make the pagination loop request forever.
    requests_mock.get(
        LAYER_URL + "/query",
        [
            {"json": {"features": [{"type": "Feature", "properties": {}, "geometry": None}]}},
            {"json": {"features": []}},
        ],
    )

    fetch_external_layers.main()

    manifest = json.loads(manifest_path.read_text())
    assert manifest["oprhp_fake"]["data_last_edit_date"] == 999
    assert manifest["oprhp_fake"]["feature_count"] == 1


def test_a_may_be_empty_source_may_come_back_with_zero_features(tmp_path, monkeypatch, requests_mock):
    """The rule fetch_all.py cannot have: OPRHP's temporary-closures layer
    honestly holds zero polygons in a good week, so zero features on an entry
    that declares `may_be_empty` is a recorded fact, not a failed run."""
    _, manifest_path = _setup(tmp_path, monkeypatch, sources=[_external(may_be_empty=True)])

    requests_mock.get(LAYER_URL, json={"editingInfo": {"dataLastEditDate": 42}})
    requests_mock.get(LAYER_URL + "/query", json={"features": []})

    fetch_external_layers.main()

    manifest = json.loads(manifest_path.read_text())
    assert manifest["oprhp_fake"]["feature_count"] == 0


def test_zero_features_without_the_flag_is_still_a_failure(tmp_path, monkeypatch, requests_mock):
    """An ArcGIS query error can arrive as HTTP 200 with an empty features
    array (lib/arcgis.py has no floor for it), so the empty-is-fine allowance
    is per-entry and never the default - a trails layer coming back empty is
    a broken fetch, exactly as it is for fetch_all.py."""
    _, manifest_path = _setup(tmp_path, monkeypatch, sources=[_external()])

    requests_mock.get(LAYER_URL, json={"editingInfo": {"dataLastEditDate": 42}})
    requests_mock.get(LAYER_URL + "/query", json={"features": []})

    with pytest.raises(SystemExit) as exc_info:
        fetch_external_layers.main()

    assert exc_info.value.code == 1
    assert not manifest_path.exists()


def test_a_failed_fetch_fails_the_run_even_on_a_may_be_empty_source(tmp_path, monkeypatch, requests_mock):
    """`may_be_empty` forgives an honest zero, never an absent answer: a
    layer whose query errored produced no fact about the parks at all, and a
    manifest written past it would look authoritative while covering
    nothing."""
    _, manifest_path = _setup(tmp_path, monkeypatch, sources=[_external(may_be_empty=True)])

    requests_mock.get(LAYER_URL, json={"editingInfo": {"dataLastEditDate": 42}})
    requests_mock.get(LAYER_URL + "/query", status_code=500)

    with pytest.raises(SystemExit) as exc_info:
        fetch_external_layers.main()

    assert exc_info.value.code == 1
    assert not manifest_path.exists()


def test_a_default_kind_source_is_never_fetched_here(tmp_path, monkeypatch, requests_mock):
    """The inverse of test_fetch_all.py's kind test: an entry without a
    `kind` is the A.T. build's and belongs to fetch_all.py's loop and its
    gate. No mock is registered for its URL, so a request to it fails this
    test loudly rather than passing silently."""
    atc_url = "https://services1.arcgis.com/fake/arcgis/rest/services/ATC/FeatureServer/0"
    _, manifest_path = _setup(
        tmp_path,
        monkeypatch,
        sources=[{"key": "centerline", "title": "A.T. Centerline", "url": atc_url}, _external()],
    )

    requests_mock.get(LAYER_URL, json={"editingInfo": {"dataLastEditDate": 42}})
    requests_mock.get(
        LAYER_URL + "/query",
        [
            {"json": {"features": [{"type": "Feature", "properties": {}, "geometry": None}]}},
            {"json": {"features": []}},
        ],
    )

    fetch_external_layers.main()

    manifest = json.loads(manifest_path.read_text())
    assert "centerline" not in manifest
    assert manifest["oprhp_fake"]["feature_count"] == 1


# --- the substitute markers (#1311) -----------------------------------------
#
# Eleven of the eighteen registered layers come from servers with no
# editingInfo, so the skip above could never fire for them and every run
# re-fetched ~195,000 features. sources.json records a substitute per entry;
# these pin that the fetcher reads it, records it, and never rounds a marker
# it could not get to "unchanged".

SERVICE_URL = "https://apps.fs.usda.gov/arcx/rest/services/EDW/Fake/MapServer?f=json"


def _pages(requests_mock, **matcher):
    """The two-page feature fetch every refetch test needs (see the first
    refetch test above for why two pages)."""
    requests_mock.get(
        LAYER_URL + "/query",
        [
            {"json": {"features": [{"type": "Feature", "properties": {}, "geometry": None}]}},
            {"json": {"features": []}},
        ],
        **matcher,
    )


def _no_statistics(request) -> bool:
    return "outstatistics" not in request.qs


def _statistics(request) -> bool:
    return "outstatistics" in request.qs


def test_a_layer_without_editing_info_skips_on_an_unchanged_service_etag(tmp_path, monkeypatch, requests_mock):
    """The Forest Service's server: no editingInfo, no date column, one ETag
    on the service description. Recorded last time, unchanged now, file on
    disk - no feature request may be made, and none is mocked."""
    raw_dir, manifest_path = _setup(
        tmp_path,
        monkeypatch,
        sources=[_external(key="usfs_fake", freshness={"marker": "etag", "url": SERVICE_URL})],
        prior_manifest={
            "usfs_fake": {
                "title": "Fake External Layer",
                "url": LAYER_URL,
                "feature_count": 1,
                "data_last_edit_date": None,
                "marker": {"kind": "etag", "url": SERVICE_URL, "value": '"1a7709d0"'},
            }
        },
    )
    (raw_dir / "usfs_fake.geojson").write_text('{"type": "FeatureCollection", "features": []}')
    requests_mock.get(LAYER_URL, json={"no": "editingInfo here"})
    requests_mock.head(SERVICE_URL, headers={"ETag": '"1a7709d0"'})

    fetch_external_layers.main()

    manifest = json.loads(manifest_path.read_text())
    assert manifest["usfs_fake"]["marker"]["value"] == '"1a7709d0"'
    assert manifest["usfs_fake"]["feature_count"] == 1


def test_a_moved_service_etag_refetches_and_records_the_new_tag(tmp_path, monkeypatch, requests_mock):
    raw_dir, manifest_path = _setup(
        tmp_path,
        monkeypatch,
        sources=[_external(key="usfs_fake", freshness={"marker": "etag", "url": SERVICE_URL})],
        prior_manifest={
            "usfs_fake": {
                "title": "Fake External Layer",
                "url": LAYER_URL,
                "feature_count": 9,
                "data_last_edit_date": None,
                "marker": {"kind": "etag", "url": SERVICE_URL, "value": '"old"'},
            }
        },
    )
    (raw_dir / "usfs_fake.geojson").write_text('{"type": "FeatureCollection", "features": []}')
    requests_mock.get(LAYER_URL, json={})
    requests_mock.head(SERVICE_URL, headers={"ETag": '"new"'})
    _pages(requests_mock)

    fetch_external_layers.main()

    manifest = json.loads(manifest_path.read_text())
    assert manifest["usfs_fake"]["marker"] == {"kind": "etag", "url": SERVICE_URL, "value": '"new"'}
    assert manifest["usfs_fake"]["feature_count"] == 1
    assert manifest["usfs_fake"]["data_last_edit_date"] is None


def test_a_layer_with_a_max_field_marker_skips_on_an_unchanged_maximum(tmp_path, monkeypatch, requests_mock):
    """NYS DEC's server: no editingInfo, but an UPDATED column, so the marker
    is one statistics query. The same /query URL serves the feature fetch;
    only the statistics shape is mocked, so a feature request here fails
    loudly rather than passing as a skip."""
    raw_dir, manifest_path = _setup(
        tmp_path,
        monkeypatch,
        sources=[_external(key="dec_fake", freshness={"kind": "arcgis_max_field", "field": "UPDATED"})],
        prior_manifest={
            "dec_fake": {
                "title": "Fake External Layer",
                "url": LAYER_URL,
                "feature_count": 3,
                "data_last_edit_date": None,
                "marker": {"kind": "max_field", "field": "UPDATED", "value": "1755475200000"},
            }
        },
    )
    (raw_dir / "dec_fake.geojson").write_text('{"type": "FeatureCollection", "features": []}')
    requests_mock.get(LAYER_URL, json={})
    requests_mock.get(
        LAYER_URL + "/query", json={"features": [{"attributes": {"marker": 1755475200000}}]}, additional_matcher=_statistics
    )

    fetch_external_layers.main()

    manifest = json.loads(manifest_path.read_text())
    assert manifest["dec_fake"]["feature_count"] == 3
    assert manifest["dec_fake"]["marker"]["value"] == "1755475200000"


def test_a_moved_maximum_refetches_and_records_it_as_a_string(tmp_path, monkeypatch, requests_mock):
    raw_dir, manifest_path = _setup(
        tmp_path,
        monkeypatch,
        sources=[_external(key="dec_fake", freshness={"kind": "arcgis_max_field", "field": "UPDATED"})],
        prior_manifest={
            "dec_fake": {
                "title": "Fake External Layer",
                "url": LAYER_URL,
                "feature_count": 3,
                "data_last_edit_date": None,
                "marker": {"kind": "max_field", "field": "UPDATED", "value": "1755475200000"},
            }
        },
    )
    (raw_dir / "dec_fake.geojson").write_text('{"type": "FeatureCollection", "features": []}')
    requests_mock.get(LAYER_URL, json={})
    requests_mock.get(
        LAYER_URL + "/query", json={"features": [{"attributes": {"marker": 1756000000000}}]}, additional_matcher=_statistics
    )
    _pages(requests_mock, additional_matcher=_no_statistics)

    fetch_external_layers.main()

    manifest = json.loads(manifest_path.read_text())
    assert manifest["dec_fake"]["marker"] == {"kind": "max_field", "field": "UPDATED", "value": "1756000000000"}
    assert manifest["dec_fake"]["feature_count"] == 1


def test_a_layer_with_no_marker_of_any_kind_is_fetched_every_run(tmp_path, monkeypatch, requests_mock):
    """NH GRANIT: `marker: none`, honestly. Fetched, and the manifest says
    there was nothing to compare - never a skip on the strength of a file
    happening to be on disk."""
    raw_dir, manifest_path = _setup(
        tmp_path,
        monkeypatch,
        sources=[_external(key="granit_fake", freshness={"marker": "none"})],
        prior_manifest={
            "granit_fake": {
                "title": "Fake External Layer",
                "url": LAYER_URL,
                "feature_count": 5,
                "data_last_edit_date": None,
                "marker": None,
            }
        },
    )
    (raw_dir / "granit_fake.geojson").write_text('{"type": "FeatureCollection", "features": []}')
    requests_mock.get(LAYER_URL, json={})
    _pages(requests_mock)

    fetch_external_layers.main()

    manifest = json.loads(manifest_path.read_text())
    assert manifest["granit_fake"]["marker"] is None
    assert manifest["granit_fake"]["feature_count"] == 1


def test_a_marker_that_cannot_be_read_costs_a_fetch_and_never_the_run(tmp_path, monkeypatch, requests_mock):
    """A metadata endpoint answering 404 is "we did not find out", which is
    a fetch - the same posture the editingInfo check has always taken - and
    the manifest records no marker rather than the stale one."""
    raw_dir, manifest_path = _setup(
        tmp_path,
        monkeypatch,
        sources=[_external(key="usfs_fake", freshness={"marker": "etag", "url": SERVICE_URL})],
        prior_manifest={
            "usfs_fake": {
                "title": "Fake External Layer",
                "url": LAYER_URL,
                "feature_count": 9,
                "data_last_edit_date": None,
                "marker": {"kind": "etag", "url": SERVICE_URL, "value": '"old"'},
            }
        },
    )
    (raw_dir / "usfs_fake.geojson").write_text('{"type": "FeatureCollection", "features": []}')
    requests_mock.get(LAYER_URL, json={})
    requests_mock.head(SERVICE_URL, status_code=404)
    _pages(requests_mock)

    fetch_external_layers.main()

    manifest = json.loads(manifest_path.read_text())
    assert manifest["usfs_fake"]["marker"] is None
    assert manifest["usfs_fake"]["feature_count"] == 1


def test_editing_info_wins_over_a_registered_substitute(tmp_path, monkeypatch, requests_mock):
    """A server that gains editingInfo is compared on it, whatever the
    registry still says - the substitute exists for the servers that lack it."""
    raw_dir, manifest_path = _setup(
        tmp_path,
        monkeypatch,
        sources=[_external(key="dec_fake", freshness={"kind": "arcgis_max_field", "field": "UPDATED"})],
        prior_manifest={
            "dec_fake": {
                "title": "Fake External Layer",
                "url": LAYER_URL,
                "feature_count": 3,
                "data_last_edit_date": 777,
            }
        },
    )
    (raw_dir / "dec_fake.geojson").write_text('{"type": "FeatureCollection", "features": []}')
    requests_mock.get(LAYER_URL, json={"editingInfo": {"dataLastEditDate": 777}})

    fetch_external_layers.main()

    manifest = json.loads(manifest_path.read_text())
    assert manifest["dec_fake"]["feature_count"] == 3
