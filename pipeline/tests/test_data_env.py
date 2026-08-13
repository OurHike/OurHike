"""Tests for lib/data_env.py - which environment's data a job writes and reads.

features/DATA_ENVIRONMENTS.md is the design. The property every test here is
some corner of: **a job publishing to one environment cannot write another
environment's keys**, and the way that is delivered is that there is exactly
one function computing a prefix and exactly one module calling it.
"""

import pytest

from lib import data_env
from lib.r2_keys import validate_key


def test_the_environments_are_the_three_the_release_process_has():
    """RELEASING.md §3's table, and no fourth. A name here that is not in that
    table is an environment nothing deploys, and a name there that is missing
    here is one nothing can publish to."""
    assert data_env.ENVIRONMENTS == ("production", "ua", "dev")


def test_production_is_the_bucket_root():
    """The asymmetry that keeps every already-published key valid. Moving
    production under a prefix would rename every URL a deployed phone requests,
    and publish()'s manifest merge is additive-only - a key cannot be renamed,
    only abandoned and served forever beside its replacement."""
    assert data_env.prefix_for("production") == ""
    assert data_env.scope_key("production", "trails.geojson") == "trails.geojson"


def test_every_other_environment_lives_under_its_own_prefix():
    assert data_env.prefix_for("ua") == "environments/ua/"
    assert data_env.scope_key("ua", "trails.geojson") == "environments/ua/trails.geojson"
    assert data_env.scope_key("dev", "conditions/closures.json") == "environments/dev/conditions/closures.json"


def test_an_unset_environment_is_a_refusal_and_not_production(monkeypatch):
    """The whole point. A caller that says nothing has not chosen production,
    it has not chosen - and the cost of guessing wrong is asymmetric to the
    point of being no contest."""
    monkeypatch.delenv(data_env.ENVIRONMENT_VAR, raising=False)
    with pytest.raises(data_env.UnknownEnvironment, match="No data environment is set"):
        data_env.resolve()


def test_a_blank_environment_is_the_same_refusal(monkeypatch):
    """`OURHIKE_DATA_ENV: ${{ vars.SOMETHING_UNSET }}` in a workflow is an
    empty string rather than an absent variable - GitHub resolves a missing
    setting to `''` rather than to an error, which is the failure mode
    .github/tests/test_repository_settings.py exists for. Both spellings of
    "nobody said" have to land in the same place."""
    monkeypatch.setenv(data_env.ENVIRONMENT_VAR, "   ")
    with pytest.raises(data_env.UnknownEnvironment):
        data_env.resolve()


def test_a_typo_is_refused_rather_than_published_somewhere_new(monkeypatch):
    """An open set would answer `uat` by writing a complete dataset into a tree
    nothing reads, nothing prunes, and nobody is looking at."""
    monkeypatch.setenv(data_env.ENVIRONMENT_VAR, "uat")
    with pytest.raises(data_env.UnknownEnvironment, match="not one of this project's data environments"):
        data_env.resolve()


def test_an_explicit_name_beats_the_variable(monkeypatch):
    monkeypatch.setenv(data_env.ENVIRONMENT_VAR, "production")
    assert data_env.resolve("ua") == "ua"


def test_a_scoped_key_round_trips():
    for environment in data_env.ENVIRONMENTS:
        scoped = data_env.scope_key(environment, "poi_shelter.geojson")
        assert data_env.unscope_key(environment, scoped) == "poi_shelter.geojson"
        assert data_env.split_key(scoped) == (environment, "poi_shelter.geojson")


def test_a_key_at_the_root_reads_back_as_productions():
    assert data_env.split_key("trails.geojson") == ("production", "trails.geojson")
    assert data_env.split_key("conditions/closures.json") == ("production", "conditions/closures.json")


def test_a_key_naming_an_environment_that_does_not_exist_is_not_read_as_productions():
    """The dangerous direction. `environments/uat/trails.geojson` is a mistake,
    and resolving it to production's own key would make the mistake's worst
    consequence - a UA-shaped write landing on live data - the thing that
    happens when somebody notices it."""
    with pytest.raises(data_env.UnknownEnvironment):
        data_env.split_key("environments/uat/trails.geojson")


def test_the_prefix_alone_names_no_object():
    with pytest.raises(data_env.UnknownEnvironment, match="names no object"):
        data_env.split_key("environments/ua/")


def test_a_base_url_gains_the_prefix_and_production_gains_nothing():
    """This is the entire client-side mechanism: config.ts builds every URL as
    `${DATA_BASE_URL}/${key}`, so an environment is a longer base and nothing
    in the app has to learn what an environment is."""
    assert data_env.base_url_for("production", "https://data.example.org") == "https://data.example.org"
    assert data_env.base_url_for("ua", "https://data.example.org") == "https://data.example.org/environments/ua"
    assert data_env.base_url_for("ua", "https://data.example.org/") == "https://data.example.org/environments/ua"


def test_a_checker_with_no_environment_reads_the_base_exactly_as_given(monkeypatch):
    """Readers may leave it unset where writers may not. A check pointed at the
    wrong environment is a wasted run; a write to the wrong environment is a
    hiker's map overwritten - so only the second one has to be typed out."""
    monkeypatch.delenv(data_env.ENVIRONMENT_VAR, raising=False)
    assert data_env.resolve_base("https://data.example.org/environments/ua/") == "https://data.example.org/environments/ua"


def test_a_checker_falls_back_to_the_published_base_variable(monkeypatch):
    monkeypatch.setenv("DATA_BASE_URL", "https://data.example.org")
    assert data_env.resolve_base(None, "ua") == "https://data.example.org/environments/ua"


def test_a_checker_with_no_base_at_all_gets_an_empty_string(monkeypatch):
    """Rather than a URL beginning with the prefix. Every caller treats empty
    as "nothing to check" and says so; a bare `environments/ua` would be
    requested and fail as a confusing 404."""
    monkeypatch.delenv("DATA_BASE_URL", raising=False)
    assert data_env.resolve_base(None, "ua") == ""


@pytest.mark.parametrize(
    "key",
    [
        "trails.geojson",
        "latest.json",
        "conditions/closures.json",
        "photos/abc123.jpg",
        "releases/2026-08-13/trails.geojson",
        "releases/index.json",
        "_internal/cells/2026-08-13/tile_001.tif",
    ],
)
def test_a_key_legal_at_the_root_is_legal_in_every_environment(key):
    """The property that makes promotion possible at all. A release folder
    legal in production and illegal in UA would mean a dataset that cannot be
    verified where it is meant to be verified, and the four-segment depth limit
    is exactly the rule that would have caused it - which is why validate_key
    strips the environment before counting."""
    assert validate_key(key) is None
    for environment in data_env.ENVIRONMENTS:
        assert validate_key(data_env.scope_key(environment, key)) is None


def test_an_illegal_name_stays_illegal_inside_an_environment():
    """The prefix is not an amnesty. A name that could never be renamed at the
    root can never be renamed in UA either - the bucket is public and the keys
    are permanent wherever they are."""
    assert validate_key("environments/ua/Trails_FINAL.geojson") is not None
    assert validate_key("environments/ua/tmp/thing.json") is not None


def test_an_unknown_environment_makes_a_key_illegal():
    problem = validate_key("environments/uat/trails.geojson")
    assert problem is not None and "uat" in problem
