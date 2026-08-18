"""lib/feature_id.py, tested at its own address (#324).

The module is the one home of the id fallback chain two artifacts must agree
on - trails.geojson and spurs.json only join because both build `{key}:{id}`
the same way - and until now it was reachable only through
test_export_spurs.py's join tests, so a regression in the chain itself would
have surfaced as a confusing spur-join failure two layers up.
"""

from lib.feature_id import resolve_feature_id


def test_globalid_wins_when_present():
    assert resolve_feature_id("side_trails", {"id": 7}, {"GlobalID": "abc-123"}, 0) == "abc-123"


def test_an_explicit_null_globalid_falls_back_to_the_features_own_id():
    """The drift this module exists to prevent, pinned: dict.get(key, default)
    only falls back when the key is ABSENT, so a raw feature carrying
    `"GlobalID": null` - a real shape some ArcGIS exports use - used to
    return None directly, and two such features collided on `f"{key}:None"`.
    The chain checks the resulting VALUE at each step."""
    assert resolve_feature_id("side_trails", {"id": 7}, {"GlobalID": None}, 0) == 7


def test_a_falsy_but_real_globalid_is_kept_verbatim():
    """The other half of the same drift: the copy this replaced checked
    truthiness instead of `is None`, so a legitimate 0 fell through the
    chain. The rule is is-None, and only is-None."""
    assert resolve_feature_id("side_trails", {"id": 7}, {"GlobalID": 0}, 0) == 0


def test_both_absent_substitutes_a_positional_id_and_warns(capsys):
    """The exporters' convention: a loud warning and carrying on, never
    raising and killing the whole batch over one bad feature."""
    resolved = resolve_feature_id("side_trails", {}, {}, 41)

    assert resolved == "generated-41"
    out = capsys.readouterr().out
    assert "WARNING" in out
    assert "side_trails" in out
    assert "41" in out


def test_the_synthetic_id_is_unique_within_a_source():
    first = resolve_feature_id("side_trails", {}, {}, 0)
    second = resolve_feature_id("side_trails", {}, {}, 1)

    assert first != second
