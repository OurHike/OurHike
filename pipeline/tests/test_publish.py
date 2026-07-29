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
