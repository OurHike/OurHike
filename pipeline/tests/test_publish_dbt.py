"""publish.py's dbt path: the pub_ writers' phone files, uploaded under the keys
their exposures name (pipeline/ELT.md, "Publish (reverse ETL)"; stage 4 of
#1793 — Rebuild the data platform as dlt → dbt: seven contracted marts, a
monthly refresh, published docs, and lighter phone downloads).

The manifest and run results here are built in test code, in the shape dbt
2.0.6 writes them (read off this branch's own target/ on 2026-10-02): an
exposure's keys under `config.meta.r2_keys`, a writer's file name under
`config.location`, its `meta.when_empty`, and each node's run timing. moto
stands in for R2, as in tests/test_publish.py; nothing here reaches a bucket.
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone

import boto3
import pytest
from moto import mock_aws

import publish
from lib import data_env, releases

BUCKET = "ourhike-test-bucket"

# Three writers in the shapes the project has: one that always writes, one
# that may keep its last file (pub_conditions_atc_updates' meta), and the
# podcast list, a live root key.
WRITERS = {
    "model.ourhike.pub_stewards": {"location": "stewards.json", "when_empty": "fail", "keys": ["stewards.json"]},
    "model.ourhike.pub_registry": {
        "location": "registry.json",
        "when_empty": "keep_last_file",
        "keys": ["registry.json"],
    },
    "model.ourhike.pub_conditions_atc_updates": {
        "location": "conditions_atc_updates.json",
        "when_empty": "keep_last_file",
        "keys": ["conditions/atc_updates.json"],
    },
    "model.ourhike.pub_podcasts_episodes": {
        "location": "podcasts_episodes.json",
        "when_empty": "fail",
        "keys": ["podcasts/episodes.json"],
    },
}


@pytest.fixture(autouse=True)
def gates(monkeypatch, tmp_path):
    """Writes on, production, and every directory publish.py reads moved under
    tmp_path, so nothing on this machine's data/ tree is read or written."""
    monkeypatch.setenv(publish.WRITE_ENABLED_ENV_VAR, "true")
    monkeypatch.setenv(data_env.ENVIRONMENT_VAR, data_env.PRODUCTION)
    monkeypatch.delenv(publish.PHONE_FILES_ENV_VAR, raising=False)
    monkeypatch.setattr(publish, "PROCESSED_DIR", tmp_path / "processed")
    monkeypatch.setattr(publish, "RAW_DIR", tmp_path / "raw")


@pytest.fixture
def s3_client():
    with mock_aws():
        client = boto3.client("s3", region_name="us-east-1")
        client.create_bucket(Bucket=BUCKET)
        yield client


def _stamp(epoch: float) -> str:
    """An instant as dbt 2.0.6 writes one: nanoseconds and a Z."""
    return datetime.fromtimestamp(epoch, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f") + "123Z"


class Project:
    """A dbt target/ and processed_dir, written the way one build leaves them."""

    def __init__(self, root):
        self.root = root
        self.target = root / "target"
        self.out = root / "out"
        self.target.mkdir(parents=True)
        self.out.mkdir(parents=True)
        self.started = time.time() - 60

    def write(self, location: str, body: str) -> None:
        (self.out / location).write_text(body, encoding="utf-8")

    def age(self, location: str, seconds: float) -> None:
        stamp = self.started - seconds
        os.utime(self.out / location, (stamp, stamp))

    def build(self, *, ran=None, status="success", writers=None, extra_exposures=None) -> None:
        writers = writers or WRITERS
        ran = list(writers) if ran is None else ran
        nodes = {
            "model.ourhike.sources": {"config": {"materialized": "table"}},
            **{
                node_id: {
                    "config": {
                        "materialized": "phone_file",
                        "location": spec["location"],
                        "meta": {"when_empty": spec["when_empty"]},
                    }
                }
                for node_id, spec in writers.items()
            },
        }
        # A writer with no keys of its own is one that shares an exposure,
        # given in `extra_exposures`, as the eight POI writers share one.
        exposures = {
            f"exposure.ourhike.{node_id.split('.')[-1]}_json": {
                "config": {"meta": {"r2_keys": spec["keys"], "format": "json"}},
                "depends_on": {"nodes": ["model.ourhike.sources", node_id]},
            }
            for node_id, spec in writers.items()
            if spec["keys"]
        }
        exposures.update(extra_exposures or {})
        (self.target / "manifest.json").write_text(json.dumps({"nodes": nodes, "exposures": exposures}))
        results = [
            {
                "unique_id": node_id,
                "status": status,
                "timing": [
                    {"name": "compile", "started_at": _stamp(self.started), "completed_at": _stamp(self.started)},
                    {"name": "execute", "started_at": _stamp(self.started), "completed_at": _stamp(self.started)},
                ],
            }
            for node_id in ran
        ]
        (self.target / "run_results.json").write_text(json.dumps({"results": results}))

    def collect(self) -> publish.DbtPhoneFiles:
        return publish.collect_dbt_phone_files(
            self.target / "manifest.json", self.target / "run_results.json", processed_dir=self.out
        )


@pytest.fixture
def project(tmp_path):
    return Project(tmp_path / "dbt")


def _write_all(project: Project, tag: str = "first") -> None:
    project.write("stewards.json", json.dumps({"stewards": [tag]}))
    project.write("registry.json", json.dumps({"sources": [tag]}))
    project.write("conditions_atc_updates.json", json.dumps({"atc_updates": [tag]}))
    project.write("podcasts_episodes.json", json.dumps({"episodes": [tag]}))


def _keys(s3_client) -> dict[str, int]:
    listing = s3_client.list_objects_v2(Bucket=BUCKET)
    return {item["Key"]: item["Size"] for item in listing.get("Contents", [])}


def _json_at(s3_client, key: str) -> dict:
    body = s3_client.get_object(Bucket=BUCKET, Key=key)["Body"].read()
    if body[:2] == b"\x1f\x8b":
        import gzip

        body = gzip.decompress(body)
    return json.loads(body)


# --- the switch -------------------------------------------------------------


def test_the_exporters_are_the_default_when_the_switch_is_unset():
    assert publish.phone_files_source() == publish.PHONE_FILES_FROM_EXPORTERS


def test_the_switch_takes_dbt(monkeypatch):
    monkeypatch.setenv(publish.PHONE_FILES_ENV_VAR, "dbt")
    assert publish.phone_files_source() == publish.PHONE_FILES_FROM_DBT


@pytest.mark.parametrize("value", ["DBT", "yes", "true", "exporter"])
def test_a_switch_value_naming_neither_pipeline_refuses(value):
    with pytest.raises(publish.UnknownPhoneFileSource, match="names neither"):
        publish.phone_files_source(value)


def test_the_writers_folder_follows_dbt_projects_processed_dir_rule(monkeypatch, tmp_path):
    monkeypatch.delenv(publish.DBT_PROCESSED_DIR_ENV_VAR, raising=False)
    assert publish.dbt_processed_dir() == (publish.DBT_PROJECT_DIR / "../data/processed/dbt").resolve()
    monkeypatch.setenv(publish.DBT_PROCESSED_DIR_ENV_VAR, str(tmp_path))
    assert publish.dbt_processed_dir() == tmp_path
    monkeypatch.setenv(publish.DBT_PROCESSED_DIR_ENV_VAR, "elsewhere")
    assert publish.dbt_processed_dir() == (publish.DBT_PROJECT_DIR / "elsewhere").resolve()


# --- what a run's writers left ----------------------------------------------


def test_each_exposure_key_maps_to_its_writers_file(project):
    _write_all(project)
    project.build()

    found = project.collect()

    assert set(found.artifacts) == {"stewards.json", "registry.json", "conditions/atc_updates.json"}
    assert set(found.live) == {"podcasts/episodes.json"}
    entry = found.artifacts["stewards.json"]
    assert entry["sha256"] == publish.sha256_file(project.out / "stewards.json")
    assert entry["size_bytes"] == (project.out / "stewards.json").stat().st_size
    assert found.kept == {}


def test_an_exposure_with_no_writer_stays_the_exporters(project):
    """conditions/weather_alerts.json's exposure names the mart it reads and no
    pub_ model: Python still writes it, so dbt owns nothing there."""
    _write_all(project)
    project.build(
        extra_exposures={
            "exposure.ourhike.conditions_weather_alerts_json": {
                "config": {"meta": {"r2_keys": ["conditions/weather_alerts.json"]}},
                "depends_on": {"nodes": ["model.ourhike.sources"]},
            }
        }
    )

    found = project.collect()

    assert "conditions/weather_alerts.json" not in found.owned


def test_a_keep_last_file_writer_that_wrote_nothing_is_kept_and_not_collected(project):
    _write_all(project)
    (project.out / "conditions_atc_updates.json").unlink()
    project.build()

    found = project.collect()

    assert "conditions/atc_updates.json" not in found.artifacts
    assert "keep_last_file" in found.kept["conditions/atc_updates.json"]
    assert "conditions/atc_updates.json" in found.owned


def test_a_file_older_than_its_writers_run_is_a_leftover_and_is_kept(project):
    """The case a directory that outlived an earlier build makes: the writer
    kept its last file, and last build's file is still on disk."""
    _write_all(project)
    project.age("registry.json", seconds=3600)
    project.build()

    found = project.collect()

    assert "registry.json" not in found.artifacts
    assert "predates this run" in found.kept["registry.json"]


def test_a_file_written_in_its_runs_first_second_is_not_a_leftover(project):
    """A filesystem that keeps mtimes to the second can stamp a fresh file a
    fraction older than the nanosecond the run began; WRITER_CLOCK_SLACK_S is
    that margin."""
    _write_all(project)
    project.age("registry.json", seconds=0.9)
    project.build()

    assert "registry.json" in project.collect().artifacts


def test_a_writer_this_invocation_did_not_run_keeps_its_last_file(project):
    """An hourly lane runs only its own writers; the monthly ones' keys are not
    this run's to publish and are carried forward."""
    _write_all(project)
    project.build(ran=["model.ourhike.pub_conditions_atc_updates"])

    found = project.collect()

    assert set(found.artifacts) == {"conditions/atc_updates.json"}
    assert "did not run" in found.kept["stewards.json"]


def test_a_writer_that_must_write_and_left_no_file_refuses(project):
    _write_all(project)
    (project.out / "stewards.json").unlink()
    project.build()

    with pytest.raises(RuntimeError, match="not a keep_last_file writer"):
        project.collect()


def test_a_writer_that_must_write_with_only_an_old_file_refuses(project):
    _write_all(project)
    project.age("stewards.json", seconds=3600)
    project.build()

    with pytest.raises(RuntimeError, match="is older than its run"):
        project.collect()


def test_an_empty_phone_file_is_never_published(project):
    _write_all(project)
    project.write("registry.json", "")
    project.build()

    with pytest.raises(RuntimeError, match="never published empty"):
        project.collect()


def test_a_writer_that_did_not_succeed_refuses(project):
    _write_all(project)
    project.build(status="error")

    with pytest.raises(RuntimeError, match="finished 'error'"):
        project.collect()


def test_run_results_that_name_no_writer_refuse(project):
    """The last dbt invocation was not the writers' (an evaluator or docs run
    after them), so every dbt key would read as kept and nothing new would
    publish, silently."""
    _write_all(project)
    project.build(ran=[])

    with pytest.raises(RuntimeError, match="names none of the"):
        project.collect()


def test_one_key_named_by_two_writers_refuses(project):
    writers = dict(WRITERS)
    writers["model.ourhike.pub_stewards_again"] = {"location": "again.json", "when_empty": "fail", "keys": ["stewards.json"]}
    _write_all(project)
    project.write("again.json", "{}")
    project.build(writers=writers)

    with pytest.raises(RuntimeError, match="one key has one writer"):
        project.collect()


POI_WRITERS = {
    "model.ourhike.pub_poi_shelter": {"location": "poi_shelter.geojson", "when_empty": "fail", "keys": []},
    "model.ourhike.pub_poi_water": {"location": "poi_water.geojson", "when_empty": "fail", "keys": []},
}


def _poi_exposure(keys):
    return {
        "exposure.ourhike.poi_by_type_geojson": {
            "config": {"meta": {"r2_keys": keys, "format": "geojson"}},
            "depends_on": {"nodes": ["model.ourhike.sources", *POI_WRITERS]},
        }
    }


def test_writers_sharing_one_exposure_each_publish_the_key_named_for_their_file(project):
    """The eight poi_<type>.geojson share the exposure poi_by_type_geojson,
    and each writer's location is its key's file name."""
    project.write("poi_shelter.geojson", '{"type": "FeatureCollection", "features": [1]}')
    project.write("poi_water.geojson", '{"type": "FeatureCollection", "features": [2, 3]}')
    project.build(writers=POI_WRITERS, extra_exposures=_poi_exposure(["poi_shelter.geojson", "poi_water.geojson"]))

    found = project.collect()

    assert found.artifacts["poi_shelter.geojson"]["sha256"] == publish.sha256_file(project.out / "poi_shelter.geojson")
    assert found.artifacts["poi_water.geojson"]["sha256"] == publish.sha256_file(project.out / "poi_water.geojson")


def test_a_shared_exposure_key_no_writer_writes_refuses(project):
    project.write("poi_shelter.geojson", "{}")
    project.write("poi_water.geojson", "{}")
    project.build(
        writers=POI_WRITERS,
        extra_exposures=_poi_exposure(["poi_shelter.geojson", "poi_water.geojson", "poi_privy.geojson"]),
    )

    with pytest.raises(RuntimeError, match="poi_privy.geojson is not the file of any"):
        project.collect()


def test_missing_dbt_artifacts_refuse_before_anything_is_read(tmp_path):
    with pytest.raises(FileNotFoundError, match="manifest"):
        publish.collect_dbt_phone_files(tmp_path / "manifest.json", tmp_path / "run_results.json", tmp_path)


def test_dbt_owns_its_keys_and_the_exporters_keep_the_rest(project):
    _write_all(project)
    (project.out / "registry.json").unlink()
    project.build()
    found = project.collect()
    exporters = {
        "stewards.json": {"path": "exporter/stewards.json", "sha256": "e1"},
        "registry.json": {"path": "exporter/registry.json", "sha256": "e2"},
        "trails.geojson": {"path": "exporter/trails.geojson", "sha256": "e3"},
    }

    merged = publish.with_dbt_phone_files(exporters, found)

    assert merged["stewards.json"]["sha256"] == found.artifacts["stewards.json"]["sha256"]
    # Kept by its dbt writer, so neither pipeline's file stands in for it.
    assert "registry.json" not in merged
    assert merged["trails.geojson"] == exporters["trails.geojson"]


# --- what reaches the bucket ------------------------------------------------


def test_a_kept_file_carries_the_previous_release_object_forward(project, s3_client):
    """The whole of the keep_last_file contract, end to end against moto.

    Run one publishes every file. Run two: the registry and ATC writers kept
    their last files and the stewards changed. Run two must upload only the
    stewards, keep naming the first registry and ATC bytes in latest.json,
    copy the first registry bytes into its own release folder, delete nothing,
    and write no empty object.
    """
    _write_all(project, "first")
    project.build()
    first = publish.publish(project.collect().artifacts, sidecars={}, photos={}, s3_client=s3_client, bucket=BUCKET)
    first_latest = _json_at(s3_client, "latest.json")["artifacts"]
    before = _keys(s3_client)

    project.write("stewards.json", json.dumps({"stewards": ["second"]}))
    (project.out / "registry.json").unlink()
    (project.out / "conditions_atc_updates.json").unlink()
    project.build()
    found = project.collect()
    second = publish.publish(publish.with_dbt_phone_files({}, found), sidecars={}, photos={}, s3_client=s3_client, bucket=BUCKET)
    after = _keys(s3_client)

    assert second["uploaded"] == ["stewards.json"]
    assert second["release"] != first["release"]
    latest = _json_at(s3_client, "latest.json")["artifacts"]
    for kept in ("registry.json", "conditions/atc_updates.json"):
        assert latest[kept]["sha256"] == first_latest[kept]["sha256"], kept
    # The release-scoped one, copied into the new folder from its flat key.
    assert _json_at(s3_client, f"releases/{second['release']}/registry.json") == {"sources": ["first"]}
    assert _json_at(s3_client, "conditions/atc_updates.json") == {"atc_updates": ["first"]}
    assert _json_at(s3_client, f"releases/{second['release']}/stewards.json") == {"stewards": ["second"]}
    assert set(before) <= set(after), f"deleted: {sorted(set(before) - set(after))}"
    assert all(size > 0 for size in after.values()), "an empty object was written"


def test_a_kept_key_with_nothing_published_before_stays_absent(project, s3_client):
    """No last good file: the key is not in the manifest at all, which a phone
    reads as unknown, and nothing is invented to fill it."""
    _write_all(project)
    (project.out / "conditions_atc_updates.json").unlink()
    project.build()

    publish.publish(project.collect().artifacts, sidecars={}, photos={}, s3_client=s3_client, bucket=BUCKET)

    assert "conditions/atc_updates.json" not in _json_at(s3_client, "latest.json")["artifacts"]
    assert "conditions/atc_updates.json" not in _keys(s3_client)


def test_conditions_files_from_dbt_stay_out_of_every_release_folder(project, s3_client):
    _write_all(project)
    project.build()

    result = publish.publish(project.collect().artifacts, sidecars={}, photos={}, s3_client=s3_client, bucket=BUCKET)

    keys = _keys(s3_client)
    assert "conditions/atc_updates.json" in keys
    assert not any(key.startswith(releases.RELEASES_PREFIX) and "conditions/" in key for key in keys)
    assert f"releases/{result['release']}/stewards.json" in keys


def test_the_podcast_list_is_never_in_the_manifest_or_a_release(project, s3_client):
    _write_all(project)
    project.build()

    publish.publish(project.collect().artifacts, sidecars={}, photos={}, s3_client=s3_client, bucket=BUCKET)

    assert not any("podcasts/" in key for key in _keys(s3_client))
    assert "podcasts/episodes.json" not in _json_at(s3_client, "latest.json")["artifacts"]


# --- main(), both ways ------------------------------------------------------


def _main_env(monkeypatch, s3_client):
    monkeypatch.setattr(publish, "collect_sidecars", dict)
    monkeypatch.setattr(publish, "collect_photos", dict)
    monkeypatch.setattr(publish.boto3, "client", lambda *a, **k: s3_client)
    monkeypatch.setenv("R2_BUCKET", BUCKET)
    monkeypatch.setenv("R2_ENDPOINT_URL", "https://unused.invalid")
    monkeypatch.setenv("R2_ACCESS_KEY_ID", "unused")
    monkeypatch.setenv("R2_SECRET_ACCESS_KEY", "unused")


def test_with_the_switch_off_main_never_reads_the_dbt_artifacts(monkeypatch, s3_client, tmp_path):
    """Today's path, untouched: the exporters' artifacts only, and a missing dbt
    target is not even looked at."""
    exported = tmp_path / "trails.geojson"
    exported.write_text('{"type": "FeatureCollection", "features": []}')
    artifacts = {"trails.geojson": {"path": str(exported), "sha256": publish.sha256_file(exported)}}
    monkeypatch.setattr(publish, "collect_artifacts", lambda: artifacts)
    monkeypatch.setattr(publish, "DBT_MANIFEST_PATH", tmp_path / "absent" / "manifest.json")
    monkeypatch.setattr(publish, "DBT_RUN_RESULTS_PATH", tmp_path / "absent" / "run_results.json")
    _main_env(monkeypatch, s3_client)

    result = publish.main()

    assert result["uploaded"] == ["trails.geojson"]


def test_with_the_switch_on_main_publishes_the_writers_files(monkeypatch, s3_client, project, capsys):
    _write_all(project)
    (project.out / "conditions_atc_updates.json").unlink()
    project.build()
    stale = project.root / "exporter_stewards.json"
    stale.write_text('{"stewards": ["the exporter"]}')
    monkeypatch.setattr(
        publish,
        "collect_artifacts",
        lambda: {"stewards.json": {"path": str(stale), "sha256": publish.sha256_file(stale)}},
    )
    monkeypatch.setattr(publish, "DBT_MANIFEST_PATH", project.target / "manifest.json")
    monkeypatch.setattr(publish, "DBT_RUN_RESULTS_PATH", project.target / "run_results.json")
    monkeypatch.setenv(publish.DBT_PROCESSED_DIR_ENV_VAR, str(project.out))
    monkeypatch.setenv(publish.PHONE_FILES_ENV_VAR, publish.PHONE_FILES_FROM_DBT)
    _main_env(monkeypatch, s3_client)

    result = publish.main()

    assert sorted(result["uploaded"]) == ["registry.json", "stewards.json"]
    assert _json_at(s3_client, "stewards.json") == {"stewards": ["first"]}
    out = capsys.readouterr().out
    assert "KEPT: conditions/atc_updates.json" in out
    assert "podcasts/episodes.json" in out


def test_with_the_switch_on_a_run_whose_writers_all_kept_is_a_quiet_no_op(monkeypatch, s3_client, project, capsys):
    writers = {node_id: spec for node_id, spec in WRITERS.items() if spec["when_empty"] == "keep_last_file"}
    project.build(writers=writers)
    monkeypatch.setattr(publish, "collect_artifacts", dict)
    monkeypatch.setattr(publish, "DBT_MANIFEST_PATH", project.target / "manifest.json")
    monkeypatch.setattr(publish, "DBT_RUN_RESULTS_PATH", project.target / "run_results.json")
    monkeypatch.setenv(publish.DBT_PROCESSED_DIR_ENV_VAR, str(project.out))
    monkeypatch.setenv(publish.PHONE_FILES_ENV_VAR, publish.PHONE_FILES_FROM_DBT)
    _main_env(monkeypatch, s3_client)

    result = publish.main()

    assert result["version_written"] is False
    assert _keys(s3_client) == {}
    assert "every phone file's writer kept its last good file" in capsys.readouterr().out


# --- the live root key ------------------------------------------------------


def test_live_puts_the_podcast_list_in_place_with_todays_headers(monkeypatch, project, s3_client):
    """export_podcasts.upload()'s object, byte for byte the writer's file, with
    its headers and no Content-Encoding."""
    monkeypatch.setenv(publish.PHONE_FILES_ENV_VAR, publish.PHONE_FILES_FROM_DBT)
    _write_all(project)
    project.build()

    result = publish.publish_live(["podcasts/episodes.json"], dbt=project.collect(), s3_client=s3_client, bucket=BUCKET)

    assert result["uploaded"] == ["podcasts/episodes.json"]
    head = s3_client.head_object(Bucket=BUCKET, Key="podcasts/episodes.json")
    assert head["ContentType"] == "application/json"
    assert head["CacheControl"] == publish.LIVE_CACHE_CONTROL
    assert "ContentEncoding" not in head
    body = s3_client.get_object(Bucket=BUCKET, Key="podcasts/episodes.json")["Body"].read()
    assert body == (project.out / "podcasts_episodes.json").read_bytes()
    assert set(_keys(s3_client)) == {"podcasts/episodes.json"}


def test_live_in_ua_writes_under_uas_prefix(monkeypatch, project, s3_client):
    monkeypatch.setenv(publish.PHONE_FILES_ENV_VAR, publish.PHONE_FILES_FROM_DBT)
    _write_all(project)
    project.build()

    publish.publish_live(
        ["podcasts/episodes.json"], dbt=project.collect(), s3_client=s3_client, bucket=BUCKET, environment=data_env.UA
    )

    assert set(_keys(s3_client)) == {"environments/ua/podcasts/episodes.json"}


def test_live_refuses_on_the_exporters_path(project, s3_client):
    _write_all(project)
    project.build()

    with pytest.raises(publish.UnknownPhoneFileSource, match="export_podcasts.py"):
        publish.publish_live(["podcasts/episodes.json"], dbt=project.collect(), s3_client=s3_client, bucket=BUCKET)
    assert _keys(s3_client) == {}


def test_live_refuses_a_key_that_is_not_a_live_root_key(monkeypatch, project, s3_client):
    monkeypatch.setenv(publish.PHONE_FILES_ENV_VAR, publish.PHONE_FILES_FROM_DBT)
    _write_all(project)
    project.build()

    with pytest.raises(RuntimeError, match="live root key"):
        publish.publish_live(["stewards.json"], dbt=project.collect(), s3_client=s3_client, bucket=BUCKET)
    assert _keys(s3_client) == {}


def test_live_with_a_kept_writer_uploads_nothing(monkeypatch, project, s3_client):
    monkeypatch.setenv(publish.PHONE_FILES_ENV_VAR, publish.PHONE_FILES_FROM_DBT)
    writers = dict(WRITERS)
    writers["model.ourhike.pub_podcasts_episodes"] = {
        **WRITERS["model.ourhike.pub_podcasts_episodes"],
        "when_empty": "keep_last_file",
    }
    _write_all(project)
    (project.out / "podcasts_episodes.json").unlink()
    project.build(writers=writers)

    result = publish.publish_live(["podcasts/episodes.json"], dbt=project.collect(), s3_client=s3_client, bucket=BUCKET)

    assert result["uploaded"] == []
    assert result["kept"] == ["podcasts/episodes.json"]
    assert _keys(s3_client) == {}


def test_live_still_needs_writes_enabled(monkeypatch, project, s3_client):
    monkeypatch.setenv(publish.PHONE_FILES_ENV_VAR, publish.PHONE_FILES_FROM_DBT)
    monkeypatch.delenv(publish.WRITE_ENABLED_ENV_VAR)
    _write_all(project)
    project.build()

    with pytest.raises(PermissionError):
        publish.publish_live(["podcasts/episodes.json"], dbt=project.collect(), s3_client=s3_client, bucket=BUCKET)
