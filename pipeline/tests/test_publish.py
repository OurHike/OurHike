"""Tests for publish.py - change-aware sync of Export's artifacts to R2.

See TECHNICAL_ARCHITECTURE.md's "Publish, change-aware end to end" section:
only artifacts whose hash actually changed get uploaded, and no new
manifest version is ever written if nothing changed - not even a no-op
version bump. Real network/S3 calls are never allowed in the suite (this
project's established convention, same as requests-mock elsewhere) - moto
mocks S3/R2 (R2 is S3-compatible) instead of hitting a real bucket.
"""

import json

import boto3
import pytest
from moto import mock_aws

import publish

BUCKET = "ourhike-test-bucket"


@pytest.fixture(autouse=True)
def enable_r2_writes(monkeypatch):
    monkeypatch.setenv(publish.WRITE_ENABLED_ENV_VAR, "true")


@pytest.fixture
def s3_client():
    with mock_aws():
        client = boto3.client("s3", region_name="us-east-1")
        client.create_bucket(Bucket=BUCKET)
        yield client


@pytest.fixture
def local_artifacts(tmp_path):
    """A tiny synthetic set of artifacts, standing in for the real
    trails/poi/elevation exports - built in test code, not read from a real
    pipeline run, per this project's small-synthetic-fixture testing
    philosophy."""
    trails_path = tmp_path / "trails.geojson"
    trails_path.write_text('{"type": "FeatureCollection", "features": []}')
    poi_path = tmp_path / "shelters.geojson"
    poi_path.write_text('{"type": "FeatureCollection", "features": [{"id": 1}]}')

    return {
        "trails.geojson": {"path": str(trails_path), "sha256": publish.sha256_file(trails_path)},
        "shelters.geojson": {"path": str(poi_path), "sha256": publish.sha256_file(poi_path)},
    }


def test_publish_requires_an_explicit_write_opt_in(monkeypatch, s3_client, local_artifacts):
    monkeypatch.delenv(publish.WRITE_ENABLED_ENV_VAR, raising=False)

    with pytest.raises(PermissionError):
        publish.publish(local_artifacts, s3_client=s3_client, bucket=BUCKET)


def test_publish_creates_the_first_manifest_when_none_exists_yet_in_the_bucket(s3_client, local_artifacts):
    result = publish.publish(local_artifacts, s3_client=s3_client, bucket=BUCKET)

    assert result["version_written"] is True
    assert set(result["uploaded"]) == {"trails.geojson", "shelters.geojson"}

    remote = json.loads(s3_client.get_object(Bucket=BUCKET, Key="latest.json")["Body"].read())
    assert remote["artifacts"]["trails.geojson"]["sha256"] == local_artifacts["trails.geojson"]["sha256"]


def test_publish_skips_an_artifact_whose_hash_is_unchanged(s3_client, local_artifacts):
    publish.publish(local_artifacts, s3_client=s3_client, bucket=BUCKET)

    # Second run, identical artifacts - nothing should upload.
    result = publish.publish(local_artifacts, s3_client=s3_client, bucket=BUCKET)

    assert result["uploaded"] == []
    assert result["skipped"] == ["shelters.geojson", "trails.geojson"] or set(result["skipped"]) == {
        "shelters.geojson",
        "trails.geojson",
    }


def test_publish_uploads_an_artifact_whose_hash_changed(s3_client, local_artifacts, tmp_path):
    publish.publish(local_artifacts, s3_client=s3_client, bucket=BUCKET)

    changed_path = tmp_path / "trails.geojson"
    changed_path.write_text('{"type": "FeatureCollection", "features": [{"id": "new"}]}')
    local_artifacts["trails.geojson"]["sha256"] = publish.sha256_file(changed_path)

    result = publish.publish(local_artifacts, s3_client=s3_client, bucket=BUCKET)

    assert result["uploaded"] == ["trails.geojson"]
    assert result["skipped"] == ["shelters.geojson"]


def test_publish_does_not_write_a_new_manifest_version_when_nothing_changed(s3_client, local_artifacts):
    first = publish.publish(local_artifacts, s3_client=s3_client, bucket=BUCKET)
    second = publish.publish(local_artifacts, s3_client=s3_client, bucket=BUCKET)

    assert first["version_written"] is True
    assert second["version_written"] is False
    assert first["version"] == second["version"]


def test_publish_preserves_previously_published_artifacts_not_present_in_this_runs_local_set(
    s3_client, local_artifacts, tmp_path
):
    """Reproduces the real go-live bug: a maintainer re-runs only
    export_trails.py (e.g. after an ATC edit) in a checkout where the rest of
    data/processed/ isn't present locally - data/ is fully gitignored and
    these artifacts run hundreds of MB to over a GB each, so a partial local
    checkout is the normal case, not an edge case (collect_artifacts()
    already tolerates this, see test_collect_skips_a_tier_that_has_not_been_built_yet).
    The R2 objects for everything else are still live, untouched by this run
    - the manifest must keep saying so, not silently drop them out from under
    a hiker's client just because this run's local set didn't include them."""
    # First publish: a "full" checkout - trails, poi, and elevation all
    # present locally, establishing a rich remote manifest.
    elevation_path = tmp_path / "elevation_profile.json"
    elevation_path.write_text('{"profile": [1, 2, 3]}')
    full_local_artifacts = dict(local_artifacts)
    full_local_artifacts["elevation_profile.json"] = {
        "path": str(elevation_path),
        "sha256": publish.sha256_file(elevation_path),
    }

    first = publish.publish(full_local_artifacts, s3_client=s3_client, bucket=BUCKET)
    assert set(first["uploaded"]) == {"trails.geojson", "shelters.geojson", "elevation_profile.json"}

    # Second publish: a partial local checkout - only trails.geojson exists
    # locally this run, and it changed. elevation_profile.json and
    # shelters.geojson are simply absent from this run's local set, the same
    # way they'd be absent from a checkout that only ran export_trails.py.
    changed_trails_path = tmp_path / "trails_changed.geojson"
    changed_trails_path.write_text('{"type": "FeatureCollection", "features": [{"id": "new"}]}')
    partial_local_artifacts = {
        "trails.geojson": {
            "path": str(changed_trails_path),
            "sha256": publish.sha256_file(changed_trails_path),
        },
    }

    second = publish.publish(partial_local_artifacts, s3_client=s3_client, bucket=BUCKET)

    assert second["uploaded"] == ["trails.geojson"]
    assert second["version_written"] is True

    remote = json.loads(s3_client.get_object(Bucket=BUCKET, Key="latest.json")["Body"].read())
    # All three artifacts from the first publish must still be listed - not
    # just the one artifact this run's local set happened to contain.
    assert set(remote["artifacts"].keys()) == {"trails.geojson", "shelters.geojson", "elevation_profile.json"}
    # The artifact that changed reflects the new content...
    assert remote["artifacts"]["trails.geojson"]["sha256"] == partial_local_artifacts["trails.geojson"]["sha256"]
    # ...while the artifacts absent from this run's local set keep the hash
    # they were published with, untouched.
    assert remote["artifacts"]["shelters.geojson"]["sha256"] == local_artifacts["shelters.geojson"]["sha256"]
    assert remote["artifacts"]["elevation_profile.json"]["sha256"] == full_local_artifacts["elevation_profile.json"]["sha256"]


def test_publish_manifest_records_one_hash_per_artifact_not_one_hash_for_everything(s3_client, local_artifacts):
    publish.publish(local_artifacts, s3_client=s3_client, bucket=BUCKET)

    remote = json.loads(s3_client.get_object(Bucket=BUCKET, Key="latest.json")["Body"].read())

    assert set(remote["artifacts"].keys()) == {"trails.geojson", "shelters.geojson"}
    assert remote["artifacts"]["trails.geojson"]["sha256"] != remote["artifacts"]["shelters.geojson"]["sha256"]
    assert "sha256" not in remote or not isinstance(remote.get("sha256"), str)


# --- Background raster archives, one per download tier -------------------
#
# The client's Downloads screen offers Light / Standard / Fine
# (client/src/lib/downloadDetail.ts), and each tier is a whole separate
# PMTiles archive built at a different max zoom. Publish has to be able to
# deliver all three, which was not true before background_z11.pmtiles
# existed: the app offered a Light download the pipeline could not produce.
#
# Naming the mapping explicitly - rather than a hardcoded tuple of filenames -
# is what makes that mismatch visible. A tier with no archive behind it is now
# a failing test rather than a download that silently 404s on a mountain.


def test_background_archives_cover_every_tier_the_client_offers():
    """The client's three levels must all be here. quad_sheet is #184's
    optional USGS sheet (#191's z14 build), published alongside the tiers
    rather than offered as a detail level - its download UX follows the
    multi-package store (#192), and until then publishing it is what makes
    it testable at all."""
    assert {"light", "standard", "fine"} <= set(publish.BACKGROUND_ARCHIVES)
    assert set(publish.BACKGROUND_ARCHIVES) - {"light", "standard", "fine"} == {
        "quad_sheet"
    }


def test_each_tier_maps_to_a_distinct_archive():
    names = list(publish.BACKGROUND_ARCHIVES.values())

    assert len(set(names)) == len(names)


def test_collect_gathers_every_background_archive_that_exists(tmp_path, monkeypatch):
    monkeypatch.setattr(publish, "PROCESSED_DIR", tmp_path)
    for name in publish.BACKGROUND_ARCHIVES.values():
        (tmp_path / name).write_bytes(b"fake pmtiles bytes for " + name.encode())

    artifacts = publish.collect_artifacts()

    for name in publish.BACKGROUND_ARCHIVES.values():
        assert name in artifacts


def test_collect_skips_a_tier_that_has_not_been_built_yet(tmp_path, monkeypatch):
    """A fresh checkout that has only run some exports still publishes what it
    has - a missing tier is not an error, just an absence."""
    monkeypatch.setattr(publish, "PROCESSED_DIR", tmp_path)
    (tmp_path / publish.BACKGROUND_ARCHIVES["standard"]).write_bytes(b"only standard")

    artifacts = publish.collect_artifacts()

    assert publish.BACKGROUND_ARCHIVES["standard"] in artifacts
    assert publish.BACKGROUND_ARCHIVES["light"] not in artifacts


def test_collect_hashes_each_archive_by_content(tmp_path, monkeypatch):
    monkeypatch.setattr(publish, "PROCESSED_DIR", tmp_path)
    light = publish.BACKGROUND_ARCHIVES["light"]
    (tmp_path / light).write_bytes(b"some bytes")

    artifacts = publish.collect_artifacts()

    assert artifacts[light]["sha256"] == publish.sha256_file(tmp_path / light)


# --- Build metadata that travels with a release ----------------------------
#
# build_state.json records the upstream freshness markers this build fetched
# against, so the scheduled check can read it back over the public URL and
# hold no R2 credentials. It rides along with a release rather than being one.


@pytest.fixture
def local_sidecars(tmp_path):
    path = tmp_path / "build_state.json"
    path.write_text(json.dumps({"version": 1, "atc": {}}))
    return {"build_state.json": {"path": str(path), "sha256": publish.sha256_file(path)}}


def test_build_state_is_uploaded_alongside_a_new_version(s3_client, local_artifacts, local_sidecars):
    result = publish.publish(local_artifacts, sidecars=local_sidecars, s3_client=s3_client, bucket=BUCKET)

    assert result["sidecars"] == ["build_state.json"]
    body = s3_client.get_object(Bucket=BUCKET, Key="build_state.json")["Body"].read()
    assert json.loads(body)["version"] == 1


def test_build_state_never_causes_a_version_bump_on_its_own(s3_client, local_artifacts, tmp_path):
    """It changes whenever an upstream is edited, including edits that alter
    no exported byte. Counted as an artifact it would bump the version for a
    no-op, which is the one rule this module exists to hold."""
    publish.publish(local_artifacts, sidecars={}, s3_client=s3_client, bucket=BUCKET)

    moved = tmp_path / "build_state_2.json"
    moved.write_text(json.dumps({"version": 1, "atc": {"centerline": {"marker": "changed"}}}))
    result = publish.publish(
        local_artifacts,
        sidecars={"build_state.json": {"path": str(moved), "sha256": publish.sha256_file(moved)}},
        s3_client=s3_client,
        bucket=BUCKET,
    )

    assert result["version_written"] is False
    assert result["uploaded"] == []


def test_build_state_is_not_uploaded_when_nothing_was_published(s3_client, local_artifacts, local_sidecars):
    """The false-fresh failure this guards: a state uploaded on a no-op run
    would describe upstreams newer than the bytes actually live in the bucket.
    The check would then compare current markers against current markers,
    report FRESH, and the map would go on serving old data with nothing
    flagging it."""
    publish.publish(local_artifacts, sidecars={}, s3_client=s3_client, bucket=BUCKET)

    publish.publish(local_artifacts, sidecars=local_sidecars, s3_client=s3_client, bucket=BUCKET)

    with pytest.raises(s3_client.exceptions.NoSuchKey):
        s3_client.get_object(Bucket=BUCKET, Key="build_state.json")


def test_build_state_is_recorded_in_the_manifest_but_not_as_an_artifact(s3_client, local_artifacts, local_sidecars):
    """Recorded so a reader can tell whether the live state describes this
    version's bytes; kept out of "artifacts" so nothing downstream can mistake
    build metadata for something a hiker downloads."""
    publish.publish(local_artifacts, sidecars=local_sidecars, s3_client=s3_client, bucket=BUCKET)

    manifest = json.loads(s3_client.get_object(Bucket=BUCKET, Key=publish.MANIFEST_KEY)["Body"].read())
    assert "build_state.json" not in manifest["artifacts"]
    assert "build_state.json" in manifest["sidecars"]


def test_collect_sidecars_finds_build_state_where_the_capture_writes_it(tmp_path, monkeypatch):
    monkeypatch.setattr(publish, "PROCESSED_DIR", tmp_path)
    (tmp_path / "build_state.json").write_text("{}")

    assert set(publish.collect_sidecars()) == {"build_state.json"}


def test_collect_sidecars_is_empty_when_no_capture_ran(tmp_path, monkeypatch):
    monkeypatch.setattr(publish, "PROCESSED_DIR", tmp_path)

    assert publish.collect_sidecars() == {}
