"""HTTP-mocked tests for fetch_all.py's skip-vs-fetch decision - the core of
the change-aware ingest work: verify unchanged sources are actually skipped
(no query call made) and changed/new sources are actually fetched, using the
real main() against a temp directory, not a reimplementation of its logic."""

import json

import pytest

import fetch_all

LAYER_URL = "https://services1.arcgis.com/fake/arcgis/rest/services/Fake/FeatureServer/0"


def _setup(tmp_path, monkeypatch, prior_manifest):
    sources = {"sources": [{"key": "fake", "title": "Fake Layer", "url": LAYER_URL}]}
    (tmp_path / "sources.json").write_text(json.dumps(sources))
    raw_dir = tmp_path / "data" / "raw"
    raw_dir.mkdir(parents=True)
    manifest_path = raw_dir / "manifest.json"
    if prior_manifest is not None:
        manifest_path.write_text(json.dumps(prior_manifest))

    monkeypatch.setattr(fetch_all, "SOURCES_PATH", tmp_path / "sources.json")
    monkeypatch.setattr(fetch_all, "RAW_DIR", raw_dir)
    monkeypatch.setattr(fetch_all, "MANIFEST_PATH", manifest_path)
    return raw_dir, manifest_path


def test_unchanged_source_is_skipped_not_refetched(tmp_path, monkeypatch, requests_mock):
    out_path, manifest_path = _setup(
        tmp_path,
        monkeypatch,
        prior_manifest={"fake": {"title": "Fake Layer", "url": LAYER_URL, "feature_count": 1, "data_last_edit_date": 123}},
    )
    (out_path / "fake.geojson").write_text('{"type": "FeatureCollection", "features": []}')

    requests_mock.get(LAYER_URL, json={"editingInfo": {"dataLastEditDate": 123}})
    # Deliberately no mock for LAYER_URL + "/query" - if the skip logic fails
    # and main() tries to fetch anyway, requests_mock raises NoMockAddress
    # and this test fails loudly, exactly the isolation guarantee wanted.

    fetch_all.main()

    manifest = json.loads(manifest_path.read_text())
    assert manifest["fake"]["data_last_edit_date"] == 123


def test_changed_source_is_refetched(tmp_path, monkeypatch, requests_mock):
    out_path, manifest_path = _setup(
        tmp_path,
        monkeypatch,
        prior_manifest={"fake": {"title": "Fake Layer", "url": LAYER_URL, "feature_count": 1, "data_last_edit_date": 111}},
    )
    (out_path / "fake.geojson").write_text('{"type": "FeatureCollection", "features": []}')

    requests_mock.get(LAYER_URL, json={"editingInfo": {"dataLastEditDate": 999}})
    # Two pages: a short-but-nonempty page followed by the empty page that
    # actually ends pagination (see test_lib_arcgis.py) - a single fixed
    # non-empty response would make fetch_layer_geojson's pagination loop
    # request forever against a mock that never runs dry.
    requests_mock.get(
        LAYER_URL + "/query",
        [
            {"json": {"features": [{"type": "Feature", "properties": {}, "geometry": None}]}},
            {"json": {"features": []}},
        ],
    )

    fetch_all.main()

    manifest = json.loads(manifest_path.read_text())
    assert manifest["fake"]["data_last_edit_date"] == 999
    assert manifest["fake"]["feature_count"] == 1


def test_first_ever_run_fetches_unconditionally(tmp_path, monkeypatch, requests_mock):
    out_path, manifest_path = _setup(tmp_path, monkeypatch, prior_manifest=None)

    requests_mock.get(LAYER_URL, json={"editingInfo": {"dataLastEditDate": 42}})
    # See test_changed_source_is_refetched: a terminal empty page is required
    # to end pagination, not just a page shorter than PAGE_SIZE.
    requests_mock.get(
        LAYER_URL + "/query",
        [
            {"json": {"features": [{"type": "Feature", "properties": {}, "geometry": None}]}},
            {"json": {"features": []}},
        ],
    )

    fetch_all.main()

    manifest = json.loads(manifest_path.read_text())
    assert manifest["fake"]["data_last_edit_date"] == 42
    assert manifest["fake"]["feature_count"] == 1


def test_zero_feature_response_is_treated_as_a_failure(tmp_path, monkeypatch, requests_mock):
    # An ArcGIS FeatureServer query error can come back as HTTP 200 with an
    # empty features array rather than a non-2xx status - lib/arcgis.py's
    # fetch_layer_geojson() has no floor for this, so a source coming back
    # with feature_count 0 must not be treated as an ordinary successful
    # fetch (see fetch_all.py's completeness check).
    out_path, manifest_path = _setup(tmp_path, monkeypatch, prior_manifest=None)

    requests_mock.get(LAYER_URL, json={"editingInfo": {"dataLastEditDate": 42}})
    requests_mock.get(LAYER_URL + "/query", json={"features": []})

    with pytest.raises(SystemExit) as exc_info:
        fetch_all.main()

    assert exc_info.value.code == 1
    # An incomplete run must not leave behind a manifest that looks
    # authoritative.
    assert not manifest_path.exists()


def test_a_source_that_is_not_a_feature_layer_is_never_fetched(tmp_path, monkeypatch, requests_mock):
    """ATC's Trail Updates are prose on a website, registered in the same
    file as the twelve ArcGIS layers (#459). Left in this loop they would
    fail their metadata check, fetch nothing, and land in the completeness
    gate as a zero-feature source - which is the gate's signal for "something
    is broken", raised on every single run for a source that was never
    supposed to be here. No mock is registered for the notices URL, so a
    request to it fails this test loudly rather than passing silently."""
    sources = {
        "sources": [
            {"key": "fake", "title": "Fake Layer", "url": LAYER_URL},
            {
                "key": "atc_trail_updates",
                "title": "A.T. Trail Updates",
                "kind": "published_notices",
                "url": "https://appalachiantrail.org/trail-updates/",
            },
        ]
    }
    (tmp_path / "sources.json").write_text(json.dumps(sources))
    raw_dir = tmp_path / "data" / "raw"
    raw_dir.mkdir(parents=True)
    manifest_path = raw_dir / "manifest.json"
    monkeypatch.setattr(fetch_all, "SOURCES_PATH", tmp_path / "sources.json")
    monkeypatch.setattr(fetch_all, "RAW_DIR", raw_dir)
    monkeypatch.setattr(fetch_all, "MANIFEST_PATH", manifest_path)

    requests_mock.get(LAYER_URL, json={"editingInfo": {"dataLastEditDate": 42}})
    requests_mock.get(
        LAYER_URL + "/query",
        [
            {"json": {"features": [{"type": "Feature", "properties": {}, "geometry": None}]}},
            {"json": {"features": []}},
        ],
    )

    fetch_all.main()

    manifest = json.loads(manifest_path.read_text())
    assert "atc_trail_updates" not in manifest
    assert manifest["fake"]["feature_count"] == 1
