"""HTTP-mocked tests for fetch_all.py's skip-vs-fetch decision - the core of
the change-aware ingest work: verify unchanged sources are actually skipped
(no query call made) and changed/new sources are actually fetched, using the
real main() against a temp directory, not a reimplementation of its logic."""

import json

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
    requests_mock.get(
        LAYER_URL + "/query",
        json={"features": [{"type": "Feature", "properties": {}, "geometry": None}]},
    )

    fetch_all.main()

    manifest = json.loads(manifest_path.read_text())
    assert manifest["fake"]["data_last_edit_date"] == 999
    assert manifest["fake"]["feature_count"] == 1


def test_first_ever_run_fetches_unconditionally(tmp_path, monkeypatch, requests_mock):
    out_path, manifest_path = _setup(tmp_path, monkeypatch, prior_manifest=None)

    requests_mock.get(LAYER_URL, json={"editingInfo": {"dataLastEditDate": 42}})
    requests_mock.get(LAYER_URL + "/query", json={"features": []})

    fetch_all.main()

    manifest = json.loads(manifest_path.read_text())
    assert manifest["fake"]["data_last_edit_date"] == 42
