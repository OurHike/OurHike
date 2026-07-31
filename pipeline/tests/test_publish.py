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
    """The tiers here must match downloadDetail.ts's three levels exactly."""
    assert set(publish.BACKGROUND_ARCHIVES) == {"light", "standard", "fine"}


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
