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
