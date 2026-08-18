"""Tests for the R2 key convention - pipeline/R2_LAYOUT.md, lib/r2_keys.py.

Two jobs here, and the second matters more than the first.

One: the rules reject what they claim to reject. Those are the small cases.

Two: **every name the pipeline can actually publish today is legal.** A
convention written after the fact that fails the artifacts already in the
bucket is not a convention, it is a rename plan - and a rename is exactly
what this layout cannot do, since publish()'s manifest merge is
additive-only and deployed clients request these keys by name. So the real
names are asserted against the real rules, and a future artifact that cannot
pass fails here rather than in a bucket nobody can undo.
"""

import pytest

import publish
from lib import data_env, r2_keys


def test_every_artifact_name_publish_can_produce_is_a_legal_key():
    names = [
        publish.MANIFEST_KEY,
        *publish.BACKGROUND_ARCHIVES.values(),
        *publish.OFFLINE_SHEET_ARCHIVES.values(),
        *publish.SIDECARS,
        # collect_artifacts() builds these from Export's manifests at run
        # time, so they have no constant to read - spelled out here exactly
        # as it spells them, which is also what makes a change to that
        # spelling show up as a failure in this file.
        "trails.geojson",
        "trails.fgb",
        "elevation_profile.json",
        "spurs.json",
        *[
            f"poi_{poi_type}.{kind}"
            for poi_type in ("shelter", "water", "campsite", "resupply", "crossing")
            for kind in ("geojson", "fgb")
        ],
        # The stretch units (#556, cut_stretches.py): the coverage index,
        # the shared context, and the per-stretch archives - spelled here
        # exactly as that module builds them, first and last id of the
        # widest plausible range so the zero-padded shape stays a legal key
        # at both ends.
        *[
            name
            for family in publish.STRETCH_FAMILIES
            for name in (
                f"{family}_stretches.json",
                f"{family}_context.pmtiles",
                f"{family}_stretch_00.pmtiles",
                f"{family}_stretch_43.pmtiles",
            )
        ],
    ]

    r2_keys.assert_valid_keys(names)


@pytest.mark.parametrize(
    "key",
    [
        "trails.geojson",
        "latest.json",
        "background_z11.pmtiles",
        "at_basemap_package_z13.pmtiles",
        "releases/index.json",
        "releases/pinned.json",
        "releases/2026-08-07/trails.geojson",
        "releases/2026-08-07-2/manifest.json",
        "_internal/cells/2026-08-07/cells_state.json",
        "_internal/cells/2026-08-07/tile_017.tif",
        # The published safety data (features/CONDITIONS_DELIVERY.md). Its own
        # prefix because it is rewritten in place daily, which a release
        # folder written once and never overwritten cannot express.
        "conditions/closures.json",
        "conditions/reports.json",
    ],
)
def test_accepts_the_layout_as_documented(key):
    assert r2_keys.validate_key(key) is None


@pytest.mark.parametrize(
    ("key", "because"),
    [
        ("Trails.geojson", "capitals"),
        ("trail data.geojson", "a space"),
        ("trails-2.geojson", "a hyphen, which is reserved for release ids"),
        ("trails.geojson.gz", "a second extension"),
        ("trails", "no extension"),
        ("trails.shp", "a format this bucket does not serve"),
        ("trails_v2.geojson", "a version in the object name"),
        ("trails_2026_08_07.geojson", "a date in the object name"),
        ("background_new.pmtiles", "a word that describes a build"),
        ("trails_final.geojson", "a word that describes a build"),
        ("tmp/trails.geojson", "an undeclared top-level prefix"),
        ("scratch/anything.json", "an undeclared top-level prefix"),
        ("releases//trails.geojson", "an empty segment"),
        ("_internal/cells/2026-08-07/detail/tile_017.tif", "one level too deep"),
        ("releases/2026-8-7/trails.geojson", "a release id that is not YYYY-MM-DD"),
    ],
)
def test_rejects_and_says_why(key, because):
    reason = r2_keys.validate_key(key)

    assert reason is not None, f"expected '{key}' to be rejected for {because}"
    assert reason, "a rejection has to come with a reason someone can act on"


def test_a_reserved_key_is_spelled_exactly_one_way():
    # `latest.json` would otherwise trip the banned-word rule ("latest"
    # describes a build, which is the whole point of banning it) - it is the
    # one mutable pointer in the bucket and is exempt by name, not by
    # weakening the rule for everyone else.
    assert r2_keys.validate_key("latest.json") is None
    assert r2_keys.validate_key("latest_trails.geojson") is not None


def test_assert_valid_keys_names_every_offender_not_just_the_first():
    with pytest.raises(ValueError) as caught:
        r2_keys.assert_valid_keys(["trails.geojson", "Bad_Name.geojson", "tmp/other.json"])

    message = str(caught.value)
    assert "Bad_Name.geojson" in message
    assert "tmp/" in message


def test_publish_refuses_a_run_carrying_an_illegal_key(monkeypatch, tmp_path):
    """The check runs before any client is built, so an unpublishable name
    costs nothing and leaves nothing half-uploaded."""
    monkeypatch.setenv(publish.WRITE_ENABLED_ENV_VAR, "true")
    monkeypatch.setenv(data_env.ENVIRONMENT_VAR, data_env.PRODUCTION)
    path = tmp_path / "artifact"
    path.write_text("{}")

    with pytest.raises(ValueError, match="R2_LAYOUT"):
        publish.publish(
            {"Trails_FINAL.geojson": {"path": str(path), "sha256": publish.sha256_file(path)}},
            sidecars={},
            s3_client=object(),
            bucket="ourhike-test-bucket",
        )
