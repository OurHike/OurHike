"""stage_release.py - the candidate release folder (#1314).

The property every test here is ultimately about is the one that makes a
weekly unattended job safe to run against a bucket real people download from:
**latest.json is never written**. Everything else - copy-forward, provenance,
manifest ordering - is about the folder being complete and honest once it
exists.

moto stands in for R2, as in test_publish.py; no real S3 call is ever made.
"""

from __future__ import annotations

import json

import boto3
import pytest
from moto import mock_aws

import publish
import stage_release
from lib import data_env, releases

BUCKET = "ourhike-test-bucket"


@pytest.fixture(autouse=True)
def enable_r2_writes(monkeypatch):
    monkeypatch.setenv(publish.WRITE_ENABLED_ENV_VAR, "true")
    monkeypatch.setenv(data_env.ENVIRONMENT_VAR, data_env.PRODUCTION)


@pytest.fixture
def s3_client():
    with mock_aws():
        client = boto3.client("s3", region_name="us-east-1")
        client.create_bucket(Bucket=BUCKET)
        yield client


@pytest.fixture
def artifacts(tmp_path):
    """Two artifacts on disk, with the hashes their exporters would record."""
    made = {}
    for name, body in (("trails.geojson", '{"features": []}'), ("spurs.json", '{"spurs": []}')):
        path = tmp_path / name
        path.write_text(body)
        made[name] = {"path": str(path), "sha256": publish.sha256_file(str(path))}
    return made


def body_at(client, key):
    return client.get_object(Bucket=BUCKET, Key=key)["Body"].read()


def keys_in(client, prefix=""):
    listed = client.list_objects_v2(Bucket=BUCKET, Prefix=prefix).get("Contents", [])
    return sorted(item["Key"] for item in listed)


class TestTheThingItMustNeverDo:
    def test_latest_json_is_not_written(self, s3_client, artifacts):
        """The whole design in one assertion. latest.json is the only object
        that decides which bytes a phone resolves, so a job that never writes
        it cannot change anybody's map however wrong it is - which is what
        lets this run weekly and unattended."""
        stage_release.stage("2026-09-09", s3_client=s3_client, bucket=BUCKET, artifacts=artifacts, sidecars={})

        assert publish.MANIFEST_KEY not in keys_in(s3_client)

    def test_no_flat_key_is_written_either(self, s3_client, artifacts):
        """A flat key is what a deployed client already requests. Writing one
        would change a live map by the back door, without ever touching the
        manifest this test's sibling watches."""
        stage_release.stage("2026-09-09", s3_client=s3_client, bucket=BUCKET, artifacts=artifacts, sidecars={})

        assert all(key.startswith("releases/") for key in keys_in(s3_client))


class TestTheFolderItWrites:
    def test_every_artifact_lands_and_the_index_lists_it_as_a_candidate(self, s3_client, artifacts):
        report = stage_release.stage("2026-09-09", s3_client=s3_client, bucket=BUCKET, artifacts=artifacts, sidecars={})

        assert keys_in(s3_client, "releases/2026-09-09/") == [
            "releases/2026-09-09/manifest.json",
            "releases/2026-09-09/spurs.json",
            "releases/2026-09-09/trails.geojson",
        ]
        index = json.loads(body_at(s3_client, releases.RELEASE_INDEX_KEY))
        [entry] = index["releases"]
        assert entry["id"] == "2026-09-09"
        assert entry["status"] == "candidate"
        assert report["uploaded"] == ["spurs.json", "trails.geojson"]

    def test_conditions_are_excluded_the_way_a_publish_excludes_them(self, s3_client, artifacts, tmp_path):
        """Safety data is rewritten in place on an hourly clock, and a closure
        that has reopened must stop being served - which an immutable folder
        cannot express."""
        closures = tmp_path / "closures.json"
        closures.write_text("[]")
        artifacts["conditions/closures.json"] = {
            "path": str(closures),
            "sha256": publish.sha256_file(str(closures)),
        }

        stage_release.stage("2026-09-09", s3_client=s3_client, bucket=BUCKET, artifacts=artifacts, sidecars={})

        assert not any("conditions" in key for key in keys_in(s3_client))

    def test_restaging_an_id_already_in_the_index_is_refused(self, s3_client, artifacts):
        """Release folders are written once and never overwritten. Restaging
        over one is the corruption the whole prefix exists to make impossible,
        and a hiker may be mid-download of it."""
        stage_release.stage("2026-09-09", s3_client=s3_client, bucket=BUCKET, artifacts=artifacts, sidecars={})

        with pytest.raises(ValueError, match="already in the release index"):
            stage_release.stage("2026-09-09", s3_client=s3_client, bucket=BUCKET, artifacts=artifacts, sidecars={})

    def test_writes_disabled_refuses_before_anything_lands(self, s3_client, artifacts, monkeypatch):
        monkeypatch.setenv(publish.WRITE_ENABLED_ENV_VAR, "false")

        with pytest.raises(PermissionError, match="R2 writes are disabled"):
            stage_release.stage("2026-09-09", s3_client=s3_client, bucket=BUCKET, artifacts=artifacts, sidecars={})
        assert keys_in(s3_client) == []


class TestCopyForward:
    def test_an_unchanged_artifact_is_copied_not_re_uploaded(self, s3_client, artifacts):
        stage_release.stage("2026-09-01", s3_client=s3_client, bucket=BUCKET, artifacts=artifacts, sidecars={})

        report = stage_release.stage("2026-09-09", s3_client=s3_client, bucket=BUCKET, artifacts=artifacts, sidecars={})

        assert report["copied"] == ["spurs.json", "trails.geojson"]
        assert report["uploaded"] == []
        assert report["previous_release"] == "2026-09-01"

    def test_the_new_folder_is_complete_even_when_nothing_changed(self, s3_client, artifacts):
        """Not a delta. A hiker's client resolves exactly one folder and must
        find everything there; a folder holding only the week's changes would
        make correctness depend on chasing a chain backwards, and one gap in
        that chain is a 404 on a mountain."""
        stage_release.stage("2026-09-01", s3_client=s3_client, bucket=BUCKET, artifacts=artifacts, sidecars={})

        stage_release.stage("2026-09-09", s3_client=s3_client, bucket=BUCKET, artifacts=artifacts, sidecars={})

        assert keys_in(s3_client, "releases/2026-09-09/") == [
            "releases/2026-09-09/manifest.json",
            "releases/2026-09-09/spurs.json",
            "releases/2026-09-09/trails.geojson",
        ]

    def test_a_changed_artifact_uploads_while_its_neighbour_copies(self, s3_client, artifacts, tmp_path):
        stage_release.stage("2026-09-01", s3_client=s3_client, bucket=BUCKET, artifacts=artifacts, sidecars={})
        moved = tmp_path / "trails.geojson"
        moved.write_text('{"features": [{"id": 1}]}')
        artifacts["trails.geojson"] = {"path": str(moved), "sha256": publish.sha256_file(str(moved))}

        report = stage_release.stage("2026-09-09", s3_client=s3_client, bucket=BUCKET, artifacts=artifacts, sidecars={})

        assert report["uploaded"] == ["trails.geojson"]
        assert report["copied"] == ["spurs.json"]

    def test_provenance_is_chased_rather_than_restated(self, s3_client, artifacts):
        """An artifact untouched for three weeks names the week it was BUILT
        in, not the week it was last copied. Restating the previous release id
        would give three folders each claiming to be where the bytes came
        from, which is three wrong answers."""
        for release_id in ("2026-08-25", "2026-09-01", "2026-09-09"):
            stage_release.stage(release_id, s3_client=s3_client, bucket=BUCKET, artifacts=artifacts, sidecars={})

        manifest = json.loads(body_at(s3_client, "releases/2026-09-09/manifest.json"))
        assert manifest["artifacts"]["spurs.json"]["origin"] == "2026-08-25"

    def test_an_unreadable_previous_manifest_stages_everything_fresh(self, s3_client, artifacts, capsys):
        """The index knows about a folder whose contents nobody can describe,
        so nothing in it is safe to copy forward. Expensive and correct."""
        s3_client.put_object(
            Bucket=BUCKET,
            Key=releases.RELEASE_INDEX_KEY,
            Body=json.dumps(releases.append_release(None, release_id="2026-09-01", version="v", created_at="a")).encode(),
        )

        report = stage_release.stage("2026-09-09", s3_client=s3_client, bucket=BUCKET, artifacts=artifacts, sidecars={})

        assert report["copied"] == []
        assert report["uploaded"] == ["spurs.json", "trails.geojson"]
        assert "no readable manifest" in capsys.readouterr().err


class TestPlanStage:
    """The decision, tested without a bucket because it is pure."""

    def test_a_matching_hash_copies_and_a_differing_one_uploads(self):
        planned = stage_release.plan_stage(
            {"same.json": {"sha256": "aaa", "path": "p"}, "moved.json": {"sha256": "bbb", "path": "q"}},
            "2026-09-01",
            {"artifacts": {"same.json": {"sha256": "aaa"}, "moved.json": {"sha256": "ccc"}}},
        )

        assert planned["same.json"]["action"] == "copy"
        assert planned["moved.json"]["action"] == "upload"

    def test_no_previous_release_uploads_everything(self):
        planned = stage_release.plan_stage({"a.json": {"sha256": "aaa", "path": "p"}}, None, {})

        assert planned["a.json"]["action"] == "upload"

    def test_an_artifact_the_previous_release_never_had_uploads(self):
        planned = stage_release.plan_stage(
            {"new.json": {"sha256": "aaa", "path": "p"}},
            "2026-09-01",
            {"artifacts": {"other.json": {"sha256": "aaa"}}},
        )

        assert planned["new.json"]["action"] == "upload"


class TestWriteOrder:
    """Which object lands when, and why it is not an implementation detail.

    Two orderings carry weight, and both fail silently if they invert - the
    bucket ends up in a state that looks finished and is not.
    """

    @staticmethod
    def recording(client, log):
        class Recorder:
            exceptions = client.exceptions

            def copy_object(self, **kwargs):
                log.append(("copy", kwargs["Key"]))
                return client.copy_object(**kwargs)

            def upload_file(self, path, bucket, key, **kwargs):
                log.append(("upload", key))
                return client.upload_file(path, bucket, key, **kwargs)

            def put_object(self, **kwargs):
                log.append(("put", kwargs["Key"]))
                return client.put_object(**kwargs)

            def get_object(self, **kwargs):
                return client.get_object(**kwargs)

        return Recorder()

    def test_the_folder_manifest_lands_after_every_artifact_in_it(self, s3_client, artifacts):
        """A manifest written early describes bytes that have not arrived. A
        reader that trusted it - the next week's copy-forward, or a rollback -
        would be told a complete folder exists when it does not."""
        log = []

        stage_release.stage(
            "2026-09-09",
            s3_client=self.recording(s3_client, log),
            bucket=BUCKET,
            artifacts=artifacts,
            sidecars={},
        )

        keys = [key for _, key in log]
        manifest_at = keys.index("releases/2026-09-09/manifest.json")
        artifact_positions = [keys.index(f"releases/2026-09-09/{name}") for name in artifacts]
        assert all(position < manifest_at for position in artifact_positions)

    def test_the_index_lands_after_the_folder_manifest(self, s3_client, artifacts):
        """The index is what advertises the folder as somewhere to look, so it
        is the last claim made. An index entry pointing at a folder whose own
        manifest has not landed is a release nothing can resolve."""
        log = []

        stage_release.stage(
            "2026-09-09",
            s3_client=self.recording(s3_client, log),
            bucket=BUCKET,
            artifacts=artifacts,
            sidecars={},
        )

        keys = [key for _, key in log]
        assert keys.index(releases.RELEASE_INDEX_KEY) > keys.index("releases/2026-09-09/manifest.json")
