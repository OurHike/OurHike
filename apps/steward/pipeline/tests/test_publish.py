"""Uploading to the private bucket, against a fake S3 client: no network, no credentials."""

from __future__ import annotations

import json

import pytest

from steward_analysis import publish

READY = {
    "STEWARD_R2_WRITE_ENABLED": "true",
    "R2_ENDPOINT_URL": "https://example.invalid",
    "STEWARD_R2_BUCKET": "example-private",
    "STEWARD_R2_ACCESS_KEY_ID": "id",
    "STEWARD_R2_SECRET_ACCESS_KEY": "secret",
}


class FakeS3:
    def __init__(self):
        self.puts: list[dict] = []

    def put_object(self, **kwargs):
        self.puts.append(kwargs)


@pytest.fixture
def out_dir(tmp_path):
    out = tmp_path / "out"
    (out / "sites").mkdir(parents=True)
    (out / "summary.json").write_text(
        json.dumps({"generated_at": "2026-10-27T00:00:00+00:00", "source": {"data_last_edited": "2026-08-20"}})
    )
    (out / "sites" / "example-trail-club.json").write_text("[]")
    (out / "sites" / "second-example-club.json").write_text("[]")
    return out


def test_a_run_uploads_under_its_own_prefix_and_moves_the_pointer_last(out_dir):
    s3 = FakeS3()
    pointer = publish.publish(out_dir, s3, "example-private", run_id="20261027T000000Z")
    keys = [p["Key"] for p in s3.puts]
    assert keys[-1] == publish.POINTER_KEY
    assert sorted(keys[:-1]) == [
        "analysis/runs/20261027T000000Z/sites/example-trail-club.json",
        "analysis/runs/20261027T000000Z/sites/second-example-club.json",
        "analysis/runs/20261027T000000Z/summary.json",
    ]
    assert json.loads(s3.puts[-1]["Body"]) == pointer
    assert pointer["prefix"] == "analysis/runs/20261027T000000Z/" and pointer["data_last_edited"] == "2026-08-20"


def test_every_object_is_marked_private_and_json(out_dir):
    s3 = FakeS3()
    publish.publish(out_dir, s3, "example-private", run_id="r")
    assert {(p["ContentType"], p["CacheControl"], p["Bucket"]) for p in s3.puts} == {
        ("application/json", "private, no-store", "example-private")
    }


def test_nothing_uploads_without_the_write_gate():
    with pytest.raises(publish.PublishRefused, match="STEWARD_R2_WRITE_ENABLED"):
        publish.check_env(READY | {"STEWARD_R2_WRITE_ENABLED": ""})


def test_missing_secrets_are_named_all_at_once():
    env = {k: v for k, v in READY.items() if k not in ("STEWARD_R2_BUCKET", "STEWARD_R2_SECRET_ACCESS_KEY")}
    with pytest.raises(publish.PublishRefused, match="STEWARD_R2_BUCKET, STEWARD_R2_SECRET_ACCESS_KEY"):
        publish.check_env(env)


def test_a_ready_environment_passes_the_check():
    publish.check_env(READY)


def test_an_empty_output_directory_is_refused_rather_than_published_as_an_empty_run(tmp_path):
    with pytest.raises(publish.PublishRefused, match="run steward_analysis.build first"):
        publish.publish(tmp_path, FakeS3(), "example-private")


def test_main_refuses_before_making_a_client_when_the_gate_is_off(out_dir, monkeypatch):
    monkeypatch.setattr(publish, "client_from_env", lambda env: pytest.fail("a client was made with the gate off"))
    with pytest.raises(publish.PublishRefused):
        publish.main(["--data", str(out_dir.parent)], env={})
