"""channels.py: moving an environment's pointer, and promoting a release into production.

The bucket copy of channels.json is the only record of which release a
phone reads (the maintainer, 2026-10-16). These hold the three rules
channels.py's docstring names: a pointer moves only to a release whose
manifest is in that environment's own tree, a move writes only its own
environment's keys and appends to their history, and a promotion moves
nothing unless every object it copied verifies. moto stands in for R2, as in
tests/test_publish.py; nothing here reaches a bucket.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import boto3
import pytest
from moto import mock_aws

import channels
import publish
from lib import data_env, releases

BUCKET = "ourhike-test-bucket"
OLD = "2026-09-24-2"
NEW = "2026-10-10-2"
WHO = {"workflow": "test", "run_id": "1", "run_url": "https://example.invalid/runs/1", "commit": "abc", "actor": "someone"}
AT = datetime(2026, 10, 16, 12, 0, tzinfo=timezone.utc)


def _photo(letter: str) -> str:
    """A key in the one shape photo_store.photo_key() builds."""
    return f"photos/{letter * 64}.jpg"


@pytest.fixture(autouse=True)
def gates(monkeypatch):
    monkeypatch.setenv(publish.WRITE_ENABLED_ENV_VAR, "true")


@pytest.fixture
def s3_client():
    with mock_aws():
        client = boto3.client("s3", region_name="us-east-1")
        client.create_bucket(Bucket=BUCKET)
        yield client


def _stage(s3_client, environment: str, release: str, files: dict[str, bytes] | None = None) -> None:
    """A release folder in `environment`'s tree, as publish.py's _stage_release leaves one: its
    files, then its manifest listing them beside a root-scoped key it does not hold."""
    files = {"trails.geojson": b'{"type": "FeatureCollection"}', "poi_water.geojson": b"[]"} if files is None else files
    for name, body in files.items():
        s3_client.put_object(Bucket=BUCKET, Key=data_env.scope_key(environment, releases.release_key(release, name)), Body=body)
    manifest = {
        "release": release,
        "artifacts": {**{name: {"sha256": "0" * 64} for name in files}, "conditions/closures.json": {}},
    }
    s3_client.put_object(Bucket=BUCKET, Key=channels.manifest_key(environment, release), Body=json.dumps(manifest).encode())


def _keys(s3_client) -> list[str]:
    return sorted(item["Key"] for item in s3_client.list_objects_v2(Bucket=BUCKET).get("Contents", []))


def _json(s3_client, key: str):
    return json.loads(s3_client.get_object(Bucket=BUCKET, Key=key)["Body"].read())


def _move(s3_client, environment: str, release: str, **kwargs):
    return channels.move_pointer(
        environment=environment,
        release=release,
        reason="test",
        s3_client=s3_client,
        bucket=BUCKET,
        provenance=WHO,
        now=AT,
        **kwargs,
    )


class TestMovingAPointer:
    def test_a_release_whose_manifest_is_not_in_this_environment_is_refused_and_nothing_is_written(self, s3_client):
        """Production's release in UA's tree is the drift DATA_RELEASES.md measured: a
        phone would refuse it and keep its last release, so the pointer would only lie."""
        _stage(s3_client, data_env.PRODUCTION, NEW)
        before = _keys(s3_client)

        with pytest.raises(channels.Refused, match="is not in the bucket"):
            _move(s3_client, data_env.UA, NEW)
        assert _keys(s3_client) == before

    def test_it_writes_the_pointer_a_phone_reads_uncached_holding_only_its_own_environment(self, s3_client):
        _stage(s3_client, data_env.UA, NEW)

        move = _move(s3_client, data_env.UA, NEW)

        assert move["moved"] is True
        stored = s3_client.get_object(Bucket=BUCKET, Key="environments/ua/channels.json")
        assert json.loads(stored["Body"].read()) == {"ua": {"v1": NEW}}
        assert stored["ContentType"] == "application/json"
        assert stored["CacheControl"] == publish.MANIFEST_CACHE_CONTROL
        assert "channels.json" not in _keys(s3_client), "production's root is not UA's to write"
        assert "channels_history.json" not in _keys(s3_client)

    def test_production_is_the_bucket_root(self, s3_client):
        _stage(s3_client, data_env.PRODUCTION, NEW)

        _move(s3_client, data_env.PRODUCTION, NEW)

        assert _json(s3_client, "channels.json") == {"production": {"v1": NEW}}
        assert not any(key.startswith("environments/") for key in _keys(s3_client))

    def test_each_move_appends_a_record_and_keeps_every_earlier_one(self, s3_client):
        _stage(s3_client, data_env.UA, OLD)
        _stage(s3_client, data_env.UA, NEW)

        _move(s3_client, data_env.UA, OLD)
        _move(s3_client, data_env.UA, NEW)

        history = _json(s3_client, "environments/ua/channels_history.json")
        assert history["environment"] == "ua"
        assert [(move["previous_release"], move["release"]) for move in history["moves"]] == [(None, OLD), (OLD, NEW)]
        assert history["moves"][1] == {
            "environment": "ua",
            "schema_version": "v1",
            "release": NEW,
            "previous_release": OLD,
            "moved_at": "2026-10-16T12:00:00Z",
            "reason": "test",
            **WHO,
        }

    def test_a_move_to_the_release_already_named_writes_nothing(self, s3_client):
        _stage(s3_client, data_env.UA, NEW)
        _move(s3_client, data_env.UA, NEW)
        history = _json(s3_client, "environments/ua/channels_history.json")

        again = _move(s3_client, data_env.UA, NEW)

        assert again["moved"] is False
        assert _json(s3_client, "environments/ua/channels_history.json") == history

    def test_another_schema_versions_entry_is_kept(self, s3_client):
        _stage(s3_client, data_env.UA, NEW)
        s3_client.put_object(Bucket=BUCKET, Key="environments/ua/channels.json", Body=json.dumps({"ua": {"v2": OLD}}).encode())

        _move(s3_client, data_env.UA, NEW)

        assert _json(s3_client, "environments/ua/channels.json") == {"ua": {"v1": NEW, "v2": OLD}}

    def test_a_history_that_cannot_be_read_is_refused_rather_than_started_again(self, s3_client):
        """Starting again would drop every earlier record of what phones were pointed at."""
        _stage(s3_client, data_env.UA, NEW)
        s3_client.put_object(Bucket=BUCKET, Key="environments/ua/channels_history.json", Body=b"not json")

        with pytest.raises(channels.Refused, match="history|not JSON"):
            _move(s3_client, data_env.UA, NEW)
        assert "environments/ua/channels.json" not in _keys(s3_client)

    @pytest.mark.parametrize(("release", "version"), [("latest", "v1"), (NEW, "1"), (NEW, "version-one")])
    def test_a_pointer_a_phone_could_not_read_is_refused(self, s3_client, release, version):
        _stage(s3_client, data_env.UA, NEW)

        with pytest.raises(channels.Refused):
            _move(s3_client, data_env.UA, release, schema_version=version)
        assert "environments/ua/channels.json" not in _keys(s3_client)

    def test_it_needs_writes_enabled(self, monkeypatch, s3_client):
        monkeypatch.delenv(publish.WRITE_ENABLED_ENV_VAR)

        with pytest.raises(PermissionError):
            _move(s3_client, data_env.UA, NEW)

    def test_who_moved_it_comes_from_the_run(self):
        assert channels.provenance_from_env(
            {
                "GITHUB_WORKFLOW": "Build",
                "GITHUB_RUN_ID": "42",
                "GITHUB_SERVER_URL": "https://github.com",
                "GITHUB_REPOSITORY": "OurHike/OurHike",
                "GITHUB_SHA": "deadbeef",
                "GITHUB_ACTOR": "a-person",
            }
        ) == {
            "workflow": "Build",
            "run_id": "42",
            "run_url": "https://github.com/OurHike/OurHike/actions/runs/42",
            "commit": "deadbeef",
            "actor": "a-person",
        }


def _promote(s3_client, **kwargs):
    return channels.promote(s3_client=s3_client, bucket=BUCKET, provenance=WHO, now=AT, **kwargs)


class TestPromoting:
    def test_it_copies_uas_release_into_production_verifies_it_and_moves_productions_pointer(self, s3_client):
        _stage(s3_client, data_env.UA, NEW)
        _move(s3_client, data_env.UA, NEW)

        result = _promote(s3_client, target=data_env.PRODUCTION)

        assert result["release"] == NEW and result["moved"] is True
        assert result["copied"] == 3
        for name in ("trails.geojson", "poi_water.geojson", "manifest.json"):
            source = s3_client.get_object(Bucket=BUCKET, Key=f"environments/ua/releases/{NEW}/{name}")["Body"].read()
            assert s3_client.get_object(Bucket=BUCKET, Key=f"releases/{NEW}/{name}")["Body"].read() == source
        assert _json(s3_client, "channels.json") == {"production": {"v1": NEW}}
        history = _json(s3_client, "channels_history.json")
        assert history["moves"][-1]["reason"] == "promoted from ua"
        assert _json(s3_client, "environments/ua/channels.json") == {"ua": {"v1": NEW}}, "UA's pointer is left alone"

    def test_a_promoted_release_is_listed_in_productions_index_so_no_publish_mints_its_id_again(self, s3_client):
        """publish.py mints ids from releases/index.json (lib/releases.next_release_id): an unlisted promoted id
        is one production's next publish that day could mint, landing its copies on the promoted folder."""
        _stage(s3_client, data_env.UA, NEW)
        s3_client.put_object(
            Bucket=BUCKET, Key="releases/index.json", Body=json.dumps({"releases": [{"id": OLD, "created_at": "x"}]}).encode()
        )

        result = _promote(s3_client, target=data_env.PRODUCTION, release=NEW)

        assert result["indexed"] is True
        assert releases.index_ids(_json(s3_client, "releases/index.json")) == [OLD, NEW]
        assert releases.next_release_id(releases.index_ids(_json(s3_client, "releases/index.json"))) != NEW
        again = _promote(s3_client, target=data_env.PRODUCTION, release=NEW)
        assert again["indexed"] is False
        assert releases.index_ids(_json(s3_client, "releases/index.json")) == [OLD, NEW]

    def test_a_copy_that_does_not_verify_writes_no_manifest_and_moves_no_pointer(self, s3_client, monkeypatch):
        _stage(s3_client, data_env.UA, NEW)
        real_copy = s3_client.copy_object

        def short_copy(**kwargs):
            if kwargs["Key"].endswith("trails.geojson"):
                s3_client.put_object(Bucket=BUCKET, Key=kwargs["Key"], Body=b"truncated")
                return {}
            return real_copy(**kwargs)

        monkeypatch.setattr(s3_client, "copy_object", short_copy)

        with pytest.raises(channels.Refused, match="do not match"):
            _promote(s3_client, target=data_env.PRODUCTION, release=NEW)
        assert f"releases/{NEW}/manifest.json" not in _keys(s3_client)
        assert "channels.json" not in _keys(s3_client)

    def test_a_source_folder_missing_a_key_its_manifest_lists_copies_nothing(self, s3_client):
        _stage(s3_client, data_env.UA, NEW)
        s3_client.delete_object(Bucket=BUCKET, Key=f"environments/ua/releases/{NEW}/trails.geojson")

        with pytest.raises(channels.Refused, match="not a whole release"):
            _promote(s3_client, target=data_env.PRODUCTION, release=NEW)
        assert not any(key.startswith("releases/") for key in _keys(s3_client))

    def test_a_rollback_to_a_release_production_already_holds_copies_nothing(self, s3_client):
        _stage(s3_client, data_env.PRODUCTION, OLD)
        _stage(s3_client, data_env.PRODUCTION, NEW)
        _move(s3_client, data_env.PRODUCTION, NEW)

        result = _promote(s3_client, target=data_env.PRODUCTION, release=OLD)

        assert result["copied"] == 0
        assert _json(s3_client, "channels.json") == {"production": {"v1": OLD}}
        assert [move["release"] for move in _json(s3_client, "channels_history.json")["moves"]] == [NEW, OLD]

    def test_a_rollback_to_a_folder_missing_a_key_is_refused(self, s3_client):
        _stage(s3_client, data_env.PRODUCTION, OLD)
        s3_client.delete_object(Bucket=BUCKET, Key=f"releases/{OLD}/poi_water.geojson")

        with pytest.raises(channels.Refused, match="lacks 1"):
            _promote(s3_client, target=data_env.PRODUCTION, release=OLD)
        assert "channels.json" not in _keys(s3_client)

    def test_a_rollback_within_ua_moves_only_uas_pointer(self, s3_client):
        _stage(s3_client, data_env.UA, OLD)
        _stage(s3_client, data_env.UA, NEW)
        _move(s3_client, data_env.UA, NEW)

        result = _promote(s3_client, target=data_env.UA, release=OLD)

        assert result["reason"] == "rolled back within ua"
        assert _json(s3_client, "environments/ua/channels.json") == {"ua": {"v1": OLD}}
        assert not any(key.startswith("releases/") or key.startswith("channels") for key in _keys(s3_client))

    def test_a_rollback_within_ua_to_a_release_it_does_not_hold_is_refused(self, s3_client):
        with pytest.raises(channels.Refused, match="cannot roll back"):
            _promote(s3_client, target=data_env.UA, release=OLD)

    def test_with_no_release_named_and_no_ua_pointer_there_is_nothing_to_promote(self, s3_client):
        _stage(s3_client, data_env.UA, NEW)

        with pytest.raises(channels.Refused, match="nothing to promote"):
            _promote(s3_client, target=data_env.PRODUCTION)
        assert not any(key.startswith("releases/") for key in _keys(s3_client))

    def test_a_promotion_carries_the_photos_its_release_references_into_productions_root(self, s3_client):
        """A phone reads `photos/` at its environment's root, never from the release folder, so a folder copy alone
        promoted cards whose photos 404 (#1878). Only the referenced photos travel; one production holds stays."""
        shelter = {"properties": {"photo_key": _photo("a"), "photos": json.dumps([{"key": _photo("b")}])}}
        hikes = {"hikes": [{"photo": {"url": _photo("c")}}, {"photo": {"url": "https://elsewhere.invalid/d.jpg"}}]}
        _stage(
            s3_client,
            data_env.UA,
            NEW,
            {
                "poi_shelter.geojson": json.dumps({"features": [shelter]}).encode(),
                "suggested_hikes.json": json.dumps(hikes).encode(),
            },
        )
        for letter in "abce":
            s3_client.put_object(Bucket=BUCKET, Key=f"environments/ua/{_photo(letter)}", Body=f"bytes of {letter}".encode())
        s3_client.put_object(Bucket=BUCKET, Key=_photo("a"), Body=b"bytes of a")

        result = _promote(s3_client, target=data_env.PRODUCTION, release=NEW)

        assert result["photos_copied"] == 2
        assert [key for key in _keys(s3_client) if key.startswith("photos/")] == [_photo("a"), _photo("b"), _photo("c")]
        assert s3_client.get_object(Bucket=BUCKET, Key=_photo("b"))["Body"].read() == b"bytes of b"

    def test_a_referenced_photo_neither_environment_holds_is_reported_and_never_stops_the_promotion(self, s3_client):
        """A rollback is promoted the same way, and one withdrawn photo must not block undoing a bad release."""
        shelter = {"properties": {"photo_key": _photo("d")}}
        _stage(s3_client, data_env.UA, NEW, {"poi_shelter.geojson": json.dumps({"features": [shelter]}).encode()})

        result = _promote(s3_client, target=data_env.PRODUCTION, release=NEW)

        assert result["moved"] is True and result["photos_copied"] == 0
        assert result["photos_absent"] == [_photo("d")]
        assert f"releases/{NEW}/manifest.json" in _keys(s3_client)

    def test_a_photo_copy_that_does_not_verify_writes_no_manifest_and_moves_no_pointer(self, s3_client, monkeypatch):
        shelter = {"properties": {"photo_key": _photo("a")}}
        _stage(s3_client, data_env.UA, NEW, {"poi_shelter.geojson": json.dumps({"features": [shelter]}).encode()})
        s3_client.put_object(Bucket=BUCKET, Key=f"environments/ua/{_photo('a')}", Body=b"bytes of a")
        real_copy = s3_client.copy_object

        def short_copy(**kwargs):
            if kwargs["Key"] == _photo("a"):
                s3_client.put_object(Bucket=BUCKET, Key=kwargs["Key"], Body=b"cut")
                return {}
            return real_copy(**kwargs)

        monkeypatch.setattr(s3_client, "copy_object", short_copy)

        with pytest.raises(channels.Refused, match="photo"):
            _promote(s3_client, target=data_env.PRODUCTION, release=NEW)
        assert f"releases/{NEW}/manifest.json" not in _keys(s3_client)
        assert "channels.json" not in _keys(s3_client)

    def test_promoting_a_release_production_already_holds_still_carries_its_missing_photos(self, s3_client):
        """The 2026-10-20 promotions copied folders and no photos; promoting one of them again fills them in."""
        files = {"poi_water.geojson": json.dumps({"features": [{"properties": {"photo_key": _photo("a")}}]}).encode()}
        _stage(s3_client, data_env.UA, NEW, files)
        _stage(s3_client, data_env.PRODUCTION, NEW, files)
        s3_client.put_object(Bucket=BUCKET, Key=f"environments/ua/{_photo('a')}", Body=b"bytes of a")

        result = _promote(s3_client, target=data_env.PRODUCTION, release=NEW)

        assert result["copied"] == 0 and result["photos_copied"] == 1
        assert _photo("a") in _keys(s3_client)

    def test_a_rollback_within_ua_copies_no_photos(self, s3_client):
        files = {"poi_water.geojson": json.dumps({"features": [{"properties": {"photo_key": _photo("a")}}]}).encode()}
        _stage(s3_client, data_env.UA, OLD, files)

        result = _promote(s3_client, target=data_env.UA, release=OLD)

        assert result["photos_copied"] == 0 and result["photos_absent"] == []

    def test_a_referenced_key_not_shaped_like_a_photo_is_never_copied_into_productions_root(self, s3_client):
        """photo_keys_in() reads whatever a file names; only `photos/<sha256>.jpg` may travel, so no file can name
        another root key (a pointer, a manifest) into production."""
        shelter = {"properties": {"photo_key": "photos/../channels.json", "photos": json.dumps([{"key": "photos/x.jpg"}])}}
        _stage(s3_client, data_env.UA, NEW, {"poi_shelter.geojson": json.dumps({"features": [shelter]}).encode()})
        s3_client.put_object(Bucket=BUCKET, Key="environments/ua/photos/x.jpg", Body=b"not content-addressed")

        result = _promote(s3_client, target=data_env.PRODUCTION, release=NEW)

        assert result["photos_copied"] == 0 and result["photos_absent"] == ["photos/../channels.json", "photos/x.jpg"]
        assert not any(key.startswith("photos/") for key in _keys(s3_client))

    def test_a_multipart_etag_is_checked_by_size_alone(self):
        assert channels._same({"size": 5, "etag": '"abc-3"'}, {"ContentLength": 5, "ETag": '"other"'})
        assert not channels._same({"size": 5, "etag": '"abc-3"'}, {"ContentLength": 4, "ETag": '"abc-3"'})
        assert not channels._same({"size": 5, "etag": '"abc"'}, {"ContentLength": 5, "ETag": '"abd"'})
        assert not channels._same({"size": 5, "etag": '"abc"'}, None)


def test_the_command_line_promotes_and_moves_nothing_else(monkeypatch, s3_client, capsys):
    _stage(s3_client, data_env.UA, NEW)
    monkeypatch.setattr(publish.boto3, "client", lambda *a, **k: s3_client)
    monkeypatch.setenv("R2_BUCKET", BUCKET)
    monkeypatch.setenv("R2_ENDPOINT_URL", "https://unused.invalid")
    monkeypatch.setenv("R2_ACCESS_KEY_ID", "unused")
    monkeypatch.setenv("R2_SECRET_ACCESS_KEY", "unused")

    result = channels.main(["promote", "--to", "production", "--release", NEW])

    assert result["moved"] is True
    assert "latest.json" not in _keys(s3_client)
    assert "moved from nothing to" in capsys.readouterr().out


def test_an_ordinary_publish_never_moves_a_pointer(s3_client, tmp_path, monkeypatch):
    """The hourly conditions bake runs publish() on a schedule; if it wrote
    channels.json, a scheduled run would move what phones read."""
    monkeypatch.setenv(data_env.ENVIRONMENT_VAR, data_env.PRODUCTION)
    monkeypatch.setattr(publish, "PROCESSED_DIR", tmp_path / "processed")
    monkeypatch.setattr(publish, "RAW_DIR", tmp_path / "raw")
    exported = tmp_path / "conditions_closures.json"
    exported.write_text('{"closures": []}')
    artifacts = {"conditions/closures.json": {"path": str(exported), "sha256": publish.sha256_file(exported)}}

    publish.publish(artifacts, sidecars={}, photos={}, s3_client=s3_client, bucket=BUCKET)

    assert not any(key.endswith((channels.CHANNELS_KEY, channels.HISTORY_KEY)) for key in _keys(s3_client))


@pytest.mark.parametrize(
    ("result", "written"),
    [
        ({"version_written": True, "release": NEW}, f"release={NEW}\n"),
        ({"version_written": False, "release": NEW}, ""),
        ({"version_written": True, "release": None}, ""),
    ],
)
def test_publish_tells_the_workflow_which_release_it_wrote(tmp_path, result, written):
    """build-reference.yml's pointer job moves UA to this, and to nothing when a run wrote no version."""
    output = tmp_path / "github_output"
    output.write_text("")

    publish.write_release_output(result, str(output))

    assert output.read_text() == written
