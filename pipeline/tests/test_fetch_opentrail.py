import copy
import json

import fetch_opentrail
from fetch_opentrail import strip_comments

SAMPLE_FC = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [-84.19, 34.63]},
            "properties": {
                "title": "Southern AT Terminus",
                "icon": "o",
                "comments": [{"text": "hi", "user": "someone", "date": "2023-12-21"}],
                "commentCount": 1,
            },
        },
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [-84.2, 34.62]},
            "properties": {"title": "Campsite", "icon": "c", "comments": [], "commentCount": 0},
        },
    ],
}


def test_strip_comments_removes_comment_fields():
    fc = strip_comments(copy.deepcopy(SAMPLE_FC))
    for feature in fc["features"]:
        assert "comments" not in feature["properties"]
        assert "commentCount" not in feature["properties"]


def test_strip_comments_preserves_other_fields():
    fc = strip_comments(copy.deepcopy(SAMPLE_FC))
    assert fc["features"][0]["properties"]["title"] == "Southern AT Terminus"
    assert fc["features"][0]["properties"]["icon"] == "o"
    assert fc["features"][1]["properties"]["title"] == "Campsite"


def test_strip_comments_handles_features_with_no_comments_key():
    fc = {
        "type": "FeatureCollection",
        "features": [{"type": "Feature", "geometry": None, "properties": {"title": "no comments here"}}],
    }
    result = strip_comments(fc)  # should not raise
    assert result["features"][0]["properties"]["title"] == "no comments here"


def test_unchanged_etag_returns_304_and_is_skipped(tmp_path, monkeypatch, requests_mock):
    """The API's own README documents ETag/If-None-Match support - a 304
    response must be treated as "nothing to do," not re-parsed as data."""
    out_path = tmp_path / "opentrail_at.geojson"
    state_path = tmp_path / "opentrail_state.json"
    out_path.write_text('{"type": "FeatureCollection", "features": []}')
    state_path.write_text(json.dumps({"etag": "abc123"}))
    monkeypatch.setattr(fetch_opentrail, "OUT_PATH", out_path)
    monkeypatch.setattr(fetch_opentrail, "STATE_PATH", state_path)

    requests_mock.get(
        fetch_opentrail.API_URL,
        request_headers={"If-None-Match": "abc123"},
        status_code=304,
    )

    fetch_opentrail.main()  # should not raise, should not rewrite files

    assert json.loads(state_path.read_text())["etag"] == "abc123"


def test_changed_etag_fetches_and_persists_new_etag(tmp_path, monkeypatch, requests_mock):
    out_path = tmp_path / "opentrail_at.geojson"
    state_path = tmp_path / "opentrail_state.json"
    out_path.write_text('{"type": "FeatureCollection", "features": []}')
    state_path.write_text(json.dumps({"etag": "old-etag"}))
    monkeypatch.setattr(fetch_opentrail, "OUT_PATH", out_path)
    monkeypatch.setattr(fetch_opentrail, "STATE_PATH", state_path)

    requests_mock.get(
        fetch_opentrail.API_URL,
        json=copy.deepcopy(SAMPLE_FC),
        headers={"ETag": "new-etag"},
    )

    fetch_opentrail.main()

    assert json.loads(state_path.read_text())["etag"] == "new-etag"
    saved = json.loads(out_path.read_text())
    assert "comments" not in saved["features"][0]["properties"]
