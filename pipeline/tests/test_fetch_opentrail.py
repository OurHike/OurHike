import copy
import json

import pytest

import fetch_opentrail
from fetch_opentrail import regression_problems, strip_comments

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


def _fc_with_n_features(n):
    """A minimal-but-valid FeatureCollection with exactly n features - used
    where the test only cares about feature count, not content."""
    return {
        "type": "FeatureCollection",
        "features": [
            {"type": "Feature", "geometry": {"type": "Point", "coordinates": [0, i]}, "properties": {"icon": "w"}}
            for i in range(n)
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


# --- regression_problems (pure function) ------------------------------------


def test_regression_problems_is_noop_when_prior_file_does_not_exist(tmp_path):
    missing = tmp_path / "does_not_exist.geojson"
    assert regression_problems(0, missing) == []


def test_regression_problems_is_noop_when_prior_file_is_unparseable(tmp_path):
    prior_path = tmp_path / "prior.geojson"
    prior_path.write_text("not valid json{{{")
    assert regression_problems(0, prior_path) == []


def test_regression_problems_is_noop_when_prior_count_is_zero(tmp_path):
    # Nothing on disk worth protecting yet - even a new count of 0 is not a
    # regression from an already-empty prior file.
    prior_path = tmp_path / "prior.geojson"
    prior_path.write_text(json.dumps(_fc_with_n_features(0)))
    assert regression_problems(0, prior_path) == []
    assert regression_problems(5, prior_path) == []


def test_regression_problems_flags_zero_new_count_against_nonzero_prior(tmp_path):
    prior_path = tmp_path / "prior.geojson"
    prior_path.write_text(json.dumps(_fc_with_n_features(10)))

    problems = regression_problems(0, prior_path)

    assert len(problems) == 1
    assert "0 features" in problems[0]
    assert "previously 10" in problems[0]


def test_regression_problems_flags_drop_over_threshold(tmp_path):
    prior_path = tmp_path / "prior.geojson"
    prior_path.write_text(json.dumps(_fc_with_n_features(10)))

    # 10 -> 4 is a 60% drop, past the 50% MAX_FEATURE_DROP_RATIO threshold.
    problems = regression_problems(4, prior_path)

    assert len(problems) == 1
    assert "4 features" in problems[0]
    assert "down from 10" in problems[0]


def test_regression_problems_allows_drop_at_or_under_threshold(tmp_path):
    prior_path = tmp_path / "prior.geojson"
    prior_path.write_text(json.dumps(_fc_with_n_features(10)))

    assert regression_problems(5, prior_path) == []  # exactly 50% - at the threshold, not past it
    assert regression_problems(6, prior_path) == []  # 40% - an ordinary-editing-sized drop
    assert regression_problems(10, prior_path) == []  # unchanged
    assert regression_problems(20, prior_path) == []  # growth is never a regression


# --- main() (integration, HTTP-mocked) ---------------------------------------


def test_empty_response_is_refused_and_leaves_prior_file_and_state_untouched(tmp_path, monkeypatch, requests_mock, capsys):
    """Reproduces the confirmed bug: main() used to accept whatever the fetch
    returned with no floor before persisting, so a well-formed-but-empty API
    response got written to OUT_PATH as-is and its ETag got persisted to
    STATE_PATH - meaning the *next* run would see 304 Not Modified against
    that new (bad) ETag and treat the degraded state as confirmed-current
    forever, with no recovery except a human noticing and deleting the state
    file by hand. Now it must refuse loudly instead, leaving both files
    exactly as they were."""
    out_path = tmp_path / "opentrail_at.geojson"
    state_path = tmp_path / "opentrail_state.json"
    prior_fc_text = json.dumps(_fc_with_n_features(10))
    prior_state_text = json.dumps({"etag": "old-etag"})
    out_path.write_text(prior_fc_text)
    state_path.write_text(prior_state_text)
    monkeypatch.setattr(fetch_opentrail, "OUT_PATH", out_path)
    monkeypatch.setattr(fetch_opentrail, "STATE_PATH", state_path)

    requests_mock.get(
        fetch_opentrail.API_URL,
        json={"type": "FeatureCollection", "features": []},
        headers={"ETag": "new-etag-bad"},
    )

    with pytest.raises(SystemExit) as exc_info:
        fetch_opentrail.main()

    assert exc_info.value.code == 1
    assert "Refusing to persist opentrail fetch" in capsys.readouterr().out
    # The old file and state must survive completely untouched - this is
    # exactly what keeps the next run's ETag-based skip logic honest instead
    # of silently locking in the bad state.
    assert out_path.read_text() == prior_fc_text
    assert state_path.read_text() == prior_state_text


def test_drastic_feature_drop_is_refused_and_leaves_prior_file_and_state_untouched(tmp_path, monkeypatch, requests_mock):
    out_path = tmp_path / "opentrail_at.geojson"
    state_path = tmp_path / "opentrail_state.json"
    prior_fc_text = json.dumps(_fc_with_n_features(10))
    prior_state_text = json.dumps({"etag": "old-etag"})
    out_path.write_text(prior_fc_text)
    state_path.write_text(prior_state_text)
    monkeypatch.setattr(fetch_opentrail, "OUT_PATH", out_path)
    monkeypatch.setattr(fetch_opentrail, "STATE_PATH", state_path)

    # 10 -> 2 is an 80% drop, well past the 50% threshold.
    requests_mock.get(
        fetch_opentrail.API_URL,
        json=_fc_with_n_features(2),
        headers={"ETag": "new-etag-bad"},
    )

    with pytest.raises(SystemExit) as exc_info:
        fetch_opentrail.main()

    assert exc_info.value.code == 1
    assert out_path.read_text() == prior_fc_text
    assert state_path.read_text() == prior_state_text


def test_moderate_feature_drop_within_threshold_is_still_persisted(tmp_path, monkeypatch, requests_mock):
    """The other direction of the same guard: an ordinary-sized drop (well
    under MAX_FEATURE_DROP_RATIO) must not be mistaken for a broken fetch -
    only a drastic collapse should ever refuse to persist."""
    out_path = tmp_path / "opentrail_at.geojson"
    state_path = tmp_path / "opentrail_state.json"
    out_path.write_text(json.dumps(_fc_with_n_features(10)))
    state_path.write_text(json.dumps({"etag": "old-etag"}))
    monkeypatch.setattr(fetch_opentrail, "OUT_PATH", out_path)
    monkeypatch.setattr(fetch_opentrail, "STATE_PATH", state_path)

    # 10 -> 6 is a 40% drop - under the 50% threshold, so this is ordinary
    # upstream editing, not a broken fetch.
    requests_mock.get(
        fetch_opentrail.API_URL,
        json=_fc_with_n_features(6),
        headers={"ETag": "new-etag-good"},
    )

    fetch_opentrail.main()  # should not raise

    assert json.loads(state_path.read_text())["etag"] == "new-etag-good"
    assert len(json.loads(out_path.read_text())["features"]) == 6
