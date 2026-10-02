"""publish.py --channels: decision 44's pointer, uploaded where phones read it.

pipeline/ELT.md, "Versions and channels (decision 44), as stage 4 builds them":
the committed channels.json names, per data environment and schema version,
the release folder a phone reads, and is "uploaded to the bucket root
(root-scoped, like latest.json) only by a dispatch, never by a push".
client/src/lib/dataRelease.ts's readDataChannel is the reader. moto stands in
for R2, as in tests/test_publish.py; nothing here reaches a bucket.
"""

from __future__ import annotations

import json

import boto3
import pytest
from moto import mock_aws

import publish
from lib import data_env, releases

BUCKET = "ourhike-test-bucket"
RELEASE = "2026-10-01"


@pytest.fixture(autouse=True)
def gates(monkeypatch, tmp_path):
    monkeypatch.setenv(publish.WRITE_ENABLED_ENV_VAR, "true")
    monkeypatch.setenv(data_env.ENVIRONMENT_VAR, data_env.PRODUCTION)
    monkeypatch.setattr(publish, "PROCESSED_DIR", tmp_path / "processed")
    monkeypatch.setattr(publish, "RAW_DIR", tmp_path / "raw")


@pytest.fixture
def s3_client():
    with mock_aws():
        client = boto3.client("s3", region_name="us-east-1")
        client.create_bucket(Bucket=BUCKET)
        yield client


def _channels(tmp_path, document) -> object:
    path = tmp_path / "channels.json"
    path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    return path


def _stage(s3_client, environment: str, release_id: str) -> None:
    """A release folder's manifest in `environment`'s tree, as _stage_release leaves one."""
    key = data_env.scope_key(environment, releases.release_key(release_id, releases.RELEASE_MANIFEST_NAME))
    s3_client.put_object(Bucket=BUCKET, Key=key, Body=json.dumps({"release": release_id, "artifacts": {}}).encode())


def _keys(s3_client) -> list[str]:
    return sorted(item["Key"] for item in s3_client.list_objects_v2(Bucket=BUCKET).get("Contents", []))


def test_the_committed_pointer_reads_as_a_phone_reads_it():
    document = publish.load_channels()

    assert set(document) == {"production", "ua"}
    for entries in document.values():
        assert publish.RELEASE_ID_PATTERN.match(entries["v1"])


def test_it_uploads_the_committed_bytes_to_productions_root_uncached(s3_client, tmp_path):
    path = _channels(tmp_path, {"production": {"v1": RELEASE}, "ua": {"v1": "2026-09-30"}})
    _stage(s3_client, data_env.PRODUCTION, RELEASE)

    result = publish.publish_channels(path=path, s3_client=s3_client, bucket=BUCKET)

    assert result == {"environment": "production", "key": "channels.json", "entries": {"v1": RELEASE}}
    stored = s3_client.get_object(Bucket=BUCKET, Key="channels.json")
    assert stored["Body"].read() == path.read_bytes()
    assert stored["ContentType"] == "application/json"
    assert stored["CacheControl"] == publish.MANIFEST_CACHE_CONTROL
    assert "ContentEncoding" not in stored


def test_ua_gets_its_own_copy_under_its_own_prefix(s3_client, tmp_path):
    path = _channels(tmp_path, {"production": {"v1": "2026-09-30"}, "ua": {"v1": RELEASE}})
    _stage(s3_client, data_env.UA, RELEASE)

    publish.publish_channels(path=path, s3_client=s3_client, bucket=BUCKET, environment=data_env.UA)

    assert "environments/ua/channels.json" in _keys(s3_client)
    assert "channels.json" not in _keys(s3_client)


def test_a_release_this_environment_does_not_hold_is_refused_and_nothing_uploads(s3_client, tmp_path):
    """Production's id in UA's tree is the drift DATA_RELEASES.md measured (14
    releases against 31, 10 in common): a pointer naming it would be refused by
    every phone, so it is refused here first."""
    path = _channels(tmp_path, {"production": {"v1": RELEASE}, "ua": {"v1": RELEASE}})
    _stage(s3_client, data_env.PRODUCTION, RELEASE)

    with pytest.raises(RuntimeError, match="is not in the bucket"):
        publish.publish_channels(path=path, s3_client=s3_client, bucket=BUCKET, environment=data_env.UA)
    assert "environments/ua/channels.json" not in _keys(s3_client)


def test_an_environment_with_no_entry_is_refused(s3_client, tmp_path):
    path = _channels(tmp_path, {"production": {"v1": RELEASE}})

    with pytest.raises(RuntimeError, match="names no release for ua"):
        publish.publish_channels(path=path, s3_client=s3_client, bucket=BUCKET, environment=data_env.UA)


@pytest.mark.parametrize(
    ("document", "message"),
    [
        ({"prod": {"v1": RELEASE}}, "not a data environment"),
        ({"production": {"1": RELEASE}}, "schema version"),
        ({"production": {"v1": "latest"}}, "not a release id"),
        ({"production": {"v1": 20261001}}, "not a release id"),
        ({"production": {}}, "not an object of schema versions"),
        ([], "not an object of data environments"),
    ],
)
def test_a_pointer_a_phone_could_not_read_is_refused(s3_client, tmp_path, document, message):
    path = _channels(tmp_path, document)

    with pytest.raises(ValueError, match=message):
        publish.publish_channels(path=path, s3_client=s3_client, bucket=BUCKET)
    assert _keys(s3_client) == []


def test_it_still_needs_writes_enabled(monkeypatch, s3_client, tmp_path):
    monkeypatch.delenv(publish.WRITE_ENABLED_ENV_VAR)
    path = _channels(tmp_path, {"production": {"v1": RELEASE}})

    with pytest.raises(PermissionError):
        publish.publish_channels(path=path, s3_client=s3_client, bucket=BUCKET)


def test_the_command_line_runs_it_and_nothing_else(monkeypatch, s3_client, tmp_path):
    path = _channels(tmp_path, {"production": {"v1": RELEASE}, "ua": {"v1": RELEASE}})
    _stage(s3_client, data_env.PRODUCTION, RELEASE)
    monkeypatch.setattr(publish, "CHANNELS_PATH", path)
    monkeypatch.setattr(publish.boto3, "client", lambda *a, **k: s3_client)
    monkeypatch.setattr(publish, "collect_artifacts", lambda: pytest.fail("--channels publishes no artifact"))
    monkeypatch.setenv("R2_BUCKET", BUCKET)
    monkeypatch.setenv("R2_ENDPOINT_URL", "https://unused.invalid")
    monkeypatch.setenv("R2_ACCESS_KEY_ID", "unused")
    monkeypatch.setenv("R2_SECRET_ACCESS_KEY", "unused")

    result = publish.main(["--channels"])

    assert result["key"] == "channels.json"
    assert "latest.json" not in _keys(s3_client)


def test_an_ordinary_publish_never_moves_the_pointer(s3_client, tmp_path):
    """The hourly conditions bake runs publish() on a schedule; if it carried
    channels.json, a merged pointer change would reach phones without the
    dispatch decision 44 reserves for it."""
    exported = tmp_path / "conditions_closures.json"
    exported.write_text('{"closures": []}')
    artifacts = {"conditions/closures.json": {"path": str(exported), "sha256": publish.sha256_file(exported)}}

    publish.publish(artifacts, sidecars={}, photos={}, s3_client=s3_client, bucket=BUCKET)

    assert not any(key.endswith("channels.json") for key in _keys(s3_client))
