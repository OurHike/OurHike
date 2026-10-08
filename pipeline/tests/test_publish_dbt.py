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
    monkeypatch.delenv(publish.BUILD_PARTIAL_ENV_VAR, raising=False)
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
                        "meta": {"when_empty": spec["when_empty"], **({"gate": spec["gate"]} if "gate" in spec else {})},
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

    def collect(self, gate=None) -> publish.DbtPhoneFiles:
        return publish.collect_dbt_phone_files(
            self.target / "manifest.json", self.target / "run_results.json", processed_dir=self.out, gate=gate
        )

    def collect_partial(self, gate=None) -> publish.DbtPhoneFiles:
        """collect(), as after a build that exited build_marts.py's PARTIAL_EXIT."""
        return publish.collect_dbt_phone_files(
            self.target / "manifest.json",
            self.target / "run_results.json",
            processed_dir=self.out,
            gate=gate,
            writers_may_fail=True,
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


def _fail(project: Project, writers: dict[str, str] | None = None, tests: dict[str, str] | None = None) -> None:
    """Rewrite the last build's run results: each of `writers` finished with that status, and each writer of `tests`
    has a not_null test of its own, attached to it in the manifest, that finished with that status."""
    manifest = json.loads((project.target / "manifest.json").read_text())
    run_results = json.loads((project.target / "run_results.json").read_text())
    for result in run_results["results"]:
        result["status"] = (writers or {}).get(result["unique_id"], result["status"])
    for writer, status in (tests or {}).items():
        test_id = f"test.ourhike.not_null_{writer.rsplit('.', 1)[-1]}_generated_at.1"
        manifest["nodes"][test_id] = {"attached_node": writer, "depends_on": {"nodes": [writer]}}
        run_results["results"].append({"unique_id": test_id, "status": status, "failures": 1})
    (project.target / "manifest.json").write_text(json.dumps(manifest))
    (project.target / "run_results.json").write_text(json.dumps(run_results))


def test_a_writer_whose_own_test_failed_refuses_because_its_file_is_already_written(project):
    """dbt builds a model before its tests, so the file is on disk: it must not pass as written."""
    _write_all(project)
    project.build()
    _fail(project, tests={"model.ourhike.pub_registry": "fail"})

    with pytest.raises(RuntimeError, match="not_null_pub_registry_generated_at.1 finished 'fail'"):
        project.collect()


def test_after_a_partial_build_a_failed_writers_key_is_kept_its_file_unread_and_the_rest_collected(project):
    """Decision 81 and soak run 531: one writer's error published nothing, though six others had written. Under
    OURHIKE_BUILD_PARTIAL a failed writer's key keeps the bucket's last copy, and so does one whose own test failed,
    whatever is on disk under their names, and every other file is collected."""
    _write_all(project)
    project.write("stewards.json", '{"stewards": ["half wri')
    project.build()
    _fail(project, writers={"model.ourhike.pub_stewards": "error"}, tests={"model.ourhike.pub_registry": "fail"})

    found = project.collect_partial()

    assert set(found.artifacts) == {"conditions/atc_updates.json"}
    assert set(found.failed) == {"stewards.json", "registry.json"}
    assert "pub_stewards failed this run (its model finished 'error')" in found.kept["stewards.json"]
    assert found.held == {}, "a failed writer is not a held source; the workflow's last step turns the run red"


def test_a_partial_build_is_read_from_the_environment_publish_conditions_sets(monkeypatch, project):
    _write_all(project)
    project.build()
    _fail(project, writers={"model.ourhike.pub_stewards": "error"})
    monkeypatch.setenv(publish.BUILD_PARTIAL_ENV_VAR, "true")

    assert "stewards.json" in project.collect().failed
    monkeypatch.setenv(publish.BUILD_PARTIAL_ENV_VAR, "")
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


# --- a gated writer: `meta.gate` names its int_closures__gate row ------------

# A writer that always writes, and two conditions writers that select no row
# while their gate row holds their source (pub_conditions_*'s meta).
GATED = {
    "model.ourhike.pub_stewards": WRITERS["model.ourhike.pub_stewards"],
    "model.ourhike.pub_conditions_nynjtc_alerts": {
        "location": "conditions_nynjtc_alerts.json",
        "when_empty": "keep_last_file",
        "gate": "nynjtc_trail_alerts",
        "keys": ["conditions/nynjtc_alerts.json"],
    },
    "model.ourhike.pub_conditions_closures": {
        "location": "conditions_closures.json",
        "when_empty": "keep_last_file",
        "gate": "ourhike_closures",
        "keys": ["conditions/closures.json"],
    },
}
PASSED = publish.GateVerdict(None)
HELD = publish.GateVerdict("NYNJTC's Trail Alerts category has no posts at all, which means the parse broke")


def _write_gated(project: Project) -> None:
    """The files of a run in which NYNJTC's writer selected no row."""
    project.write("stewards.json", json.dumps({"stewards": ["first"]}))
    project.write("conditions_closures.json", json.dumps({"closures": []}))


def test_a_held_sources_file_is_kept_and_every_other_file_is_still_collected(project):
    """One held source no longer stops every conditions file: its key is kept,
    so the phone keeps its last copy, and is marked held so the run fails."""
    _write_gated(project)
    project.build(writers=GATED)

    found = project.collect(gate={"nynjtc_trail_alerts": HELD, "ourhike_closures": PASSED})

    assert set(found.artifacts) == {"stewards.json", "conditions/closures.json"}
    assert found.held == {"conditions/nynjtc_alerts.json": f"nynjtc_trail_alerts is held: {HELD.held_because}"}
    assert HELD.held_because in found.kept["conditions/nynjtc_alerts.json"]


def test_an_unreviewed_file_is_kept_without_failing_the_run(project):
    """export_atc_updates.py and export_work_projects.py exit 0 for a file
    nobody reviewed yet, so its hold keeps the file and is not `held`."""
    _write_gated(project)
    project.build(writers=GATED)
    unreviewed = publish.GateVerdict("nobody has reviewed it", awaiting_review=True)

    found = project.collect(gate={"nynjtc_trail_alerts": unreviewed, "ourhike_closures": PASSED})

    assert "conditions/nynjtc_alerts.json" in found.kept
    assert found.held == {}


def test_a_gated_writer_that_wrote_nothing_while_its_gate_passed_refuses(project):
    """Why when_empty defaults to 'fail': a writer that selected no row by
    mistake must not pass as one that chose to. The gate row tells them apart."""
    _write_gated(project)
    project.build(writers=GATED)

    with pytest.raises(RuntimeError, match="holds nothing for nynjtc_trail_alerts"):
        project.collect(gate={"nynjtc_trail_alerts": PASSED, "ourhike_closures": PASSED})


def test_a_gated_writer_that_wrote_a_held_sources_file_refuses(project):
    _write_gated(project)
    project.write("conditions_nynjtc_alerts.json", json.dumps({"nynjtc_alerts": []}))
    project.build(writers=GATED)

    with pytest.raises(RuntimeError, match="while int_closures__gate holds nynjtc_trail_alerts"):
        project.collect(gate={"nynjtc_trail_alerts": HELD, "ourhike_closures": PASSED})


def test_a_gated_writer_whose_gate_has_no_row_refuses(project):
    _write_gated(project)
    project.build(writers=GATED)

    with pytest.raises(RuntimeError, match="has no row for it"):
        project.collect(gate={"ourhike_closures": PASSED})


def test_the_gate_is_not_read_when_no_gated_writer_ran(monkeypatch, project):
    """The monthly lane runs no conditions writer, and its warehouse holds no gate."""
    _write_gated(project)
    project.build(writers=GATED, ran=["model.ourhike.pub_stewards"])

    def unread(manifest, warehouse=None):
        raise AssertionError("the gate was read")

    monkeypatch.setattr(publish, "read_gate", unread)

    assert set(project.collect().artifacts) == {"stewards.json"}


def test_the_gate_is_read_from_the_relation_the_manifest_names(tmp_path):
    import duckdb

    warehouse = tmp_path / "warehouse.duckdb"
    with duckdb.connect(str(warehouse)) as con:
        con.execute("create schema intermediate")
        con.execute(
            "create table intermediate.int_closures__gate as select * from (values "
            "('nynjtc_trail_alerts', 'the parse broke', false), ('ourhike_closures', null, false), "
            "('atc_trail_updates', 'nobody has reviewed it', true)) as t (source_key, held_because, awaiting_review)"
        )
    manifest = {
        "nodes": {
            "model.ourhike.int_closures__gate": {
                "resource_type": "model",
                "name": "int_closures__gate",
                "schema": "intermediate",
                "alias": "int_closures__gate",
            }
        }
    }

    assert publish.read_gate(manifest, warehouse) == {
        "nynjtc_trail_alerts": publish.GateVerdict("the parse broke"),
        "ourhike_closures": publish.GateVerdict(None),
        "atc_trail_updates": publish.GateVerdict("nobody has reviewed it", awaiting_review=True),
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


# --- a v2 file: its release folder is its only home -------------------------

# The stewards writer and its v2, in the shape the eleven real v2 writers have
# (pub_poi_water_v2: location poi_water_v2.geojson, key v2/poi_water.geojson).
V2_WRITERS = {
    "model.ourhike.pub_stewards": WRITERS["model.ourhike.pub_stewards"],
    "model.ourhike.pub_stewards_v2": {"location": "stewards_v2.json", "when_empty": "fail", "keys": ["v2/stewards.json"]},
}


def _write_v2(project: Project, tag: str = "first", v2_tag: str | None = None) -> None:
    project.write("stewards.json", json.dumps({"stewards": [tag]}))
    project.write("stewards_v2.json", json.dumps({"format": 2, "stewards": [v2_tag or tag]}))


@pytest.mark.parametrize(
    ("name", "only_in_a_release"),
    [
        ("v2/poi_water.geojson", True),
        ("v2/trail_miles.json", True),
        ("v3/poi_water.geojson", True),
        ("poi_water.geojson", False),
        ("trail_graph_cell_n40w074.json", False),
        # Root-scoped families keep their versions under declared prefixes.
        ("conditions/v2/notices.json", False),
        ("podcasts/v2/episodes.json", False),
    ],
)
def test_only_a_release_scoped_key_under_a_version_segment_is_release_only(name, only_in_a_release):
    assert publish.release_only(name) is only_in_a_release


def _folder(s3_client, release_id: str) -> dict:
    return _json_at(s3_client, f"releases/{release_id}/{releases.RELEASE_MANIFEST_NAME}")


def test_a_v2_file_is_uploaded_into_the_release_folder_and_never_at_the_root(project, s3_client):
    """Monthly run 29 (refresh-reference.yml 37726904273): the eleven v2 keys
    went to the root, which lib/r2_keys.py refuses before any upload. Each
    is now uploaded into the folder this publish stages and listed in that
    folder's manifest only: latest.json describes the flat keys, and every
    reader of it fetches what it lists at the root."""
    _write_v2(project)
    project.build(writers=V2_WRITERS)

    result = publish.publish(project.collect().artifacts, sidecars={}, photos={}, s3_client=s3_client, bucket=BUCKET)

    keys = _keys(s3_client)
    assert not any(key.startswith("v2/") for key in keys)
    assert _json_at(s3_client, f"releases/{result['release']}/v2/stewards.json") == {"format": 2, "stewards": ["first"]}
    latest = _json_at(s3_client, "latest.json")
    assert "v2/stewards.json" not in latest["artifacts"]
    assert latest["release"] == result["release"]
    written = project.collect().artifacts["v2/stewards.json"]
    entry = _folder(s3_client, result["release"])["artifacts"]["v2/stewards.json"]
    assert entry["sha256"] == written["sha256"]
    assert entry["size_bytes"] == written["size_bytes"]
    assert entry["transfer_bytes"] > 0
    assert "v2/stewards.json" in result["uploaded"]
    assert "v2/stewards.json" in result["release_artifacts"]


def test_an_unchanged_v2_file_is_copied_into_the_next_release_from_the_last(project, s3_client):
    _write_v2(project, "first")
    project.build(writers=V2_WRITERS)
    first = publish.publish(project.collect().artifacts, sidecars={}, photos={}, s3_client=s3_client, bucket=BUCKET)

    project.write("stewards.json", json.dumps({"stewards": ["second"]}))
    project.build(writers=V2_WRITERS)
    second = publish.publish(project.collect().artifacts, sidecars={}, photos={}, s3_client=s3_client, bucket=BUCKET)

    assert second["uploaded"] == ["stewards.json"]
    assert "v2/stewards.json" in second["skipped"]
    assert second["release"] != first["release"]
    assert _json_at(s3_client, f"releases/{second['release']}/v2/stewards.json") == {"format": 2, "stewards": ["first"]}
    first_entry = _folder(s3_client, first["release"])["artifacts"]["v2/stewards.json"]
    # Carried forward whole but for `change`, which described the last hop.
    assert _folder(s3_client, second["release"])["artifacts"]["v2/stewards.json"] == {
        key: value for key, value in first_entry.items() if key != "change"
    }
    assert not any(key.startswith("v2/") for key in _keys(s3_client))


def test_a_v2_file_whose_writer_kept_is_carried_into_the_next_release(project, s3_client):
    _write_v2(project, "first")
    project.build(writers=V2_WRITERS)
    first = publish.publish(project.collect().artifacts, sidecars={}, photos={}, s3_client=s3_client, bucket=BUCKET)

    project.write("stewards.json", json.dumps({"stewards": ["second"]}))
    project.build(writers=V2_WRITERS, ran=["model.ourhike.pub_stewards"])
    found = project.collect()
    assert "v2/stewards.json" in found.kept
    second = publish.publish(found.artifacts, sidecars={}, photos={}, s3_client=s3_client, bucket=BUCKET)

    assert _json_at(s3_client, f"releases/{second['release']}/v2/stewards.json") == {"format": 2, "stewards": ["first"]}
    assert (
        _folder(s3_client, second["release"])["artifacts"]["v2/stewards.json"]["sha256"]
        == _folder(s3_client, first["release"])["artifacts"]["v2/stewards.json"]["sha256"]
    )


def test_a_release_with_no_v2_files_of_its_own_still_carries_the_last_ones(project, s3_client):
    """Every folder is complete (lib/releases.py): a publish that wrote no v2
    file, such as an exporter's, still stages one holding the last ones, or a
    build reading v2 from that folder would find nothing there."""
    _write_v2(project, "first")
    project.build(writers=V2_WRITERS)
    publish.publish(project.collect().artifacts, sidecars={}, photos={}, s3_client=s3_client, bucket=BUCKET)

    exported = project.root / "exporter_stewards.json"
    exported.write_text('{"stewards": ["the exporter"]}')
    artifacts = {"stewards.json": {"path": str(exported), "sha256": publish.sha256_file(exported)}}
    second = publish.publish(artifacts, sidecars={}, photos={}, s3_client=s3_client, bucket=BUCKET)

    assert _json_at(s3_client, f"releases/{second['release']}/v2/stewards.json") == {"format": 2, "stewards": ["first"]}
    assert "v2/stewards.json" in _folder(s3_client, second["release"])["artifacts"]


def test_a_changed_v2_file_alone_writes_a_version_and_a_release(project, s3_client):
    _write_v2(project, "first")
    project.build(writers=V2_WRITERS)
    first = publish.publish(project.collect().artifacts, sidecars={}, photos={}, s3_client=s3_client, bucket=BUCKET)

    _write_v2(project, "first", v2_tag="second")
    project.build(writers=V2_WRITERS)
    second = publish.publish(project.collect().artifacts, sidecars={}, photos={}, s3_client=s3_client, bucket=BUCKET)

    assert second["uploaded"] == ["v2/stewards.json"]
    assert second["version_written"]
    assert second["version"] != first["version"]
    assert second["release"] != first["release"]
    assert _json_at(s3_client, "latest.json")["release"] == second["release"]
    assert _json_at(s3_client, f"releases/{second['release']}/v2/stewards.json") == {"format": 2, "stewards": ["second"]}
    # The v1 file is copied from its flat key, as before.
    assert _json_at(s3_client, f"releases/{second['release']}/stewards.json") == {"stewards": ["first"]}
    # The first folder is untouched.
    assert _json_at(s3_client, f"releases/{first['release']}/v2/stewards.json") == {"format": 2, "stewards": ["first"]}


def test_a_changed_v2_feature_collection_is_described_against_the_last_release(project, s3_client):
    """describe_changes reads a release-only file's last copy from the folder
    latest.json named: a flat read would find nothing and every v2 change
    would reach a phone as one nobody could describe."""
    writers = {
        "model.ourhike.pub_stewards": WRITERS["model.ourhike.pub_stewards"],
        "model.ourhike.pub_poi_water_v2": {
            "location": "poi_water_v2.geojson",
            "when_empty": "fail",
            "keys": ["v2/poi_water.geojson"],
        },
    }

    def water(*ids: str) -> str:
        features = [{"type": "Feature", "geometry": None, "properties": {"id": poi_id}} for poi_id in ids]
        return json.dumps({"type": "FeatureCollection", "features": features})

    project.write("stewards.json", json.dumps({"stewards": ["first"]}))
    project.write("poi_water_v2.geojson", water("spring-1"))
    project.build(writers=writers)
    publish.publish(project.collect().artifacts, sidecars={}, photos={}, s3_client=s3_client, bucket=BUCKET)

    project.write("poi_water_v2.geojson", water("spring-1", "spring-2"))
    project.build(writers=writers)
    second = publish.publish(project.collect().artifacts, sidecars={}, photos={}, s3_client=s3_client, bucket=BUCKET)

    change = _folder(s3_client, second["release"])["artifacts"]["v2/poi_water.geojson"]["change"]
    assert change["added"] == 1, change
    assert "unreadable" not in json.dumps(change)


def test_a_withdrawn_poi_types_v2_file_is_not_carried_forward(project, s3_client, tmp_path):
    crossings = tmp_path / "poi_crossing_v2.geojson"
    crossings.write_text('{"type": "FeatureCollection", "features": []}')
    _write_v2(project, "first")
    project.build(writers=V2_WRITERS)
    first = {
        **project.collect().artifacts,
        "v2/poi_crossing.geojson": {"path": str(crossings), "sha256": publish.sha256_file(crossings)},
    }
    publish.publish(first, sidecars={}, photos={}, s3_client=s3_client, bucket=BUCKET)

    project.write("stewards.json", json.dumps({"stewards": ["second"]}))
    project.build(writers=V2_WRITERS)
    second = publish.publish(project.collect().artifacts, sidecars={}, photos={}, s3_client=s3_client, bucket=BUCKET)

    folder = _folder(s3_client, second["release"])["artifacts"]
    assert "v2/poi_crossing.geojson" not in folder
    assert "v2/stewards.json" in folder


def test_a_release_whose_manifest_is_gone_refuses_a_v2_publish_before_any_upload(project, s3_client):
    """latest.json names a folder whose manifest is not there, so its v2 files
    can be neither compared nor carried forward."""
    _write_v2(project)
    project.build(writers=V2_WRITERS)
    s3_client.put_object(
        Bucket=BUCKET, Key="latest.json", Body=json.dumps({"version": "v0", "release": "2026-01-01", "artifacts": {}})
    )

    with pytest.raises(RuntimeError, match="is not there"):
        publish.publish(project.collect().artifacts, sidecars={}, photos={}, s3_client=s3_client, bucket=BUCKET)

    assert set(_keys(s3_client)) == {"latest.json"}


def test_a_conditions_only_publish_never_reads_a_release_folder(project, s3_client):
    """The hourly lane publishes `conditions/` alone, and a closure must not
    wait on a release folder: with the last folder's manifest gone, it still
    publishes."""
    _write_all(project, "first")
    project.build()
    first = publish.publish(project.collect().artifacts, sidecars={}, photos={}, s3_client=s3_client, bucket=BUCKET)
    s3_client.delete_object(Bucket=BUCKET, Key=f"releases/{first['release']}/{releases.RELEASE_MANIFEST_NAME}")

    project.write("conditions_atc_updates.json", json.dumps({"atc_updates": ["second"]}))
    project.build()
    second = publish.publish(project.collect().artifacts, sidecars={}, photos={}, s3_client=s3_client, bucket=BUCKET)

    assert second["uploaded"] == ["conditions/atc_updates.json"]
    assert second["release"] == first["release"]
    assert _json_at(s3_client, "conditions/atc_updates.json") == {"atc_updates": ["second"]}


def test_staging_refuses_a_release_only_file_it_has_nowhere_to_copy_from(s3_client):
    manifest = {"version": "v1", "artifacts": {"v2/stewards.json": {"sha256": "a"}}}

    with pytest.raises(RuntimeError, match="no release to copy them from"):
        publish._stage_release(s3_client, BUCKET, "", "2026-10-08", manifest, [], previous_release=None)

    assert _keys(s3_client) == {}


# --- the confirm job's reads: what UA serves -----------------------------------


@pytest.fixture
def public_bucket(tmp_path):
    """A public bucket over HTTP on localhost, answering urllib's own agent 403
    as data.ourhike.org did (measured 2026-10-08), and recording each
    request's agent."""
    import http.server
    import threading

    root = tmp_path / "public"
    root.mkdir()
    agents: list[str] = []

    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(root), **kwargs)

        def do_GET(self):  # noqa: N802 - http.server's name
            agent = self.headers.get("User-Agent", "")
            agents.append(agent)
            if agent.startswith("Python-urllib"):
                self.send_error(403)
                return
            super().do_GET()

        def log_message(self, *args):
            pass

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    def put(key: str, document: dict) -> None:
        path = root / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(document))

    try:
        yield {"base": f"http://127.0.0.1:{server.server_address[1]}", "put": put, "agents": agents}
    finally:
        server.shutdown()


def test_the_confirm_read_names_itself_and_takes_v2_entries_from_the_release_folder(public_bucket):
    public_bucket["put"](
        "environments/ua/latest.json",
        {"release": "2026-10-08", "artifacts": {"stewards.json": {"sha256": "flat"}}},
    )
    public_bucket["put"](
        "environments/ua/releases/2026-10-08/manifest.json",
        {"artifacts": {"stewards.json": {"sha256": "flat"}, "v2/stewards.json": {"sha256": "folder"}}},
    )

    served, urls = publish.served_entries(public_bucket["base"], "ua", ["stewards.json", "v2/stewards.json"])

    assert served == {"stewards.json": {"sha256": "flat"}, "v2/stewards.json": {"sha256": "folder"}}
    assert urls == [
        f"{public_bucket['base']}/environments/ua/latest.json",
        f"{public_bucket['base']}/environments/ua/releases/2026-10-08/manifest.json",
    ]
    assert public_bucket["agents"] == [publish.USER_AGENT, publish.USER_AGENT]


def test_the_confirm_read_needs_no_release_folder_without_a_v2_file(public_bucket):
    public_bucket["put"]("environments/ua/latest.json", {"artifacts": {"stewards.json": {"sha256": "flat"}}})

    served, urls = publish.served_entries(public_bucket["base"], "ua", ["stewards.json"])

    assert served == {"stewards.json": {"sha256": "flat"}}
    assert len(urls) == 1


def test_the_confirm_read_refuses_a_v2_file_when_latest_json_names_no_release(public_bucket):
    public_bucket["put"]("environments/ua/latest.json", {"artifacts": {}})

    with pytest.raises(RuntimeError, match="names no release"):
        publish.served_entries(public_bucket["base"], "ua", ["v2/stewards.json"])


# --- the detail family: one writer's file, one object per hike ----------------

DETAIL_WRITERS = {
    "model.ourhike.pub_stewards": WRITERS["model.ourhike.pub_stewards"],
    "model.ourhike.pub_suggested_hikes_detail": {
        "location": "suggested_hikes_detail.json",
        "when_empty": "keep_last_file",
        "keys": [publish.DETAIL_FAMILY_KEY],
    },
}
DETAILS = [
    {"id": "nynjtc_favorite_hikes:50", "summary": 'A "loop" past Ä\u00e9 falls\twith a tab'},
    {"id": "nynjtc_favorite_hikes:7", "summary": None},
]


def _write_details(project: Project, details=DETAILS) -> None:
    project.write("stewards.json", json.dumps({"stewards": ["first"]}))
    project.write("suggested_hikes_detail.json", json.dumps({"details": details}))


def test_the_detail_writers_file_is_cut_into_one_object_per_hike(project):
    """Monthly run 29 published `suggested_hikes_detail_{number}.json` as it
    stood, braces and all. Each detail is its own object under the
    exporter's key and in the exporter's bytes."""
    _write_details(project)
    project.build(writers=DETAIL_WRITERS)

    found = project.collect()

    assert publish.DETAIL_FAMILY_KEY not in found.artifacts
    assert sorted(key for key in found.artifacts if key.startswith("suggested_hikes_detail")) == [
        "suggested_hikes_detail_50.json",
        "suggested_hikes_detail_7.json",
    ]
    for detail in DETAILS:
        number = detail["id"].rsplit(":", 1)[1]
        entry = found.artifacts[f"suggested_hikes_detail_{number}.json"]
        written = publish.from_manifest_path(entry["path"]).read_bytes()
        assert written == json.dumps(detail, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        assert entry["sha256"] == publish.sha256_file(publish.from_manifest_path(entry["path"]))
    assert {"suggested_hikes_detail_50.json", publish.DETAIL_FAMILY_KEY} <= found.owned


def test_a_detail_cut_leaves_no_object_from_an_earlier_cut(project):
    _write_details(project)
    project.build(writers=DETAIL_WRITERS)
    project.collect()

    _write_details(project, DETAILS[:1])
    project.build(writers=DETAIL_WRITERS)
    found = project.collect()

    assert [key for key in found.artifacts if key.startswith("suggested_hikes_detail")] == ["suggested_hikes_detail_50.json"]
    assert sorted(path.name for path in (project.out / publish.DETAIL_CUT_DIRNAME).iterdir()) == ["50.json"]


def test_a_detail_id_no_phone_could_ask_for_refuses_before_anything_is_cut(project):
    _write_details(project, [{"id": "nynjtc_favorite_hikes:hike-vista-loop-trail"}])
    project.build(writers=DETAIL_WRITERS)

    with pytest.raises(ValueError, match="detailKeyFor"):
        project.collect()
    assert not (project.out / publish.DETAIL_CUT_DIRNAME).exists()


def test_a_detail_writer_that_kept_keeps_the_family_and_cuts_nothing(project):
    _write_details(project)
    (project.out / "suggested_hikes_detail.json").unlink()
    project.build(writers=DETAIL_WRITERS)

    found = project.collect()

    assert publish.DETAIL_FAMILY_KEY in found.kept
    assert not any(key.startswith("suggested_hikes_detail") for key in found.artifacts)


def test_once_dbt_owns_the_detail_family_no_exporters_detail_is_published(project):
    _write_details(project)
    project.build(writers=DETAIL_WRITERS)
    found = project.collect()
    exporters = {
        "suggested_hikes_detail_50.json": {"path": "exporter/50.json", "sha256": "e50"},
        # A number this run's cut does not have: still the exporter's, still dropped.
        "suggested_hikes_detail_99.json": {"path": "exporter/99.json", "sha256": "e99"},
        "trails.geojson": {"path": "exporter/trails.geojson", "sha256": "e3"},
    }

    merged = publish.with_dbt_phone_files(exporters, found)

    assert merged["suggested_hikes_detail_50.json"]["sha256"] == found.artifacts["suggested_hikes_detail_50.json"]["sha256"]
    assert "suggested_hikes_detail_99.json" not in merged
    assert merged["trails.geojson"] == exporters["trails.geojson"]


def test_the_cut_details_and_a_v2_file_publish_together(project, s3_client):
    """Run 29's whole refusal in one publish: every key passes the layout
    check, the details land flat and in the folder, the v2 file in the folder
    alone."""
    writers = {**DETAIL_WRITERS, "model.ourhike.pub_stewards_v2": V2_WRITERS["model.ourhike.pub_stewards_v2"]}
    _write_details(project)
    project.write("stewards_v2.json", json.dumps({"format": 2, "stewards": ["first"]}))
    project.build(writers=writers)

    result = publish.publish(project.collect().artifacts, sidecars={}, photos={}, s3_client=s3_client, bucket=BUCKET)

    keys = _keys(s3_client)
    latest = _json_at(s3_client, "latest.json")["artifacts"]
    for name in ("suggested_hikes_detail_50.json", "suggested_hikes_detail_7.json"):
        assert name in keys
        assert name in latest
        assert f"releases/{result['release']}/{name}" in keys
    assert f"releases/{result['release']}/v2/stewards.json" in keys
    assert "v2/stewards.json" not in latest
    assert _json_at(s3_client, "suggested_hikes_detail_50.json") == DETAILS[0]


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


def _main_on_dbt(monkeypatch, s3_client, project, verdicts):
    monkeypatch.setattr(publish, "collect_artifacts", dict)
    monkeypatch.setattr(publish, "DBT_MANIFEST_PATH", project.target / "manifest.json")
    monkeypatch.setattr(publish, "DBT_RUN_RESULTS_PATH", project.target / "run_results.json")
    monkeypatch.setattr(publish, "read_gate", lambda manifest, warehouse=None: verdicts)
    monkeypatch.setenv(publish.DBT_PROCESSED_DIR_ENV_VAR, str(project.out))
    monkeypatch.setenv(publish.PHONE_FILES_ENV_VAR, publish.PHONE_FILES_FROM_DBT)
    _main_env(monkeypatch, s3_client)


def test_main_publishes_every_other_file_and_then_fails_for_a_held_one(monkeypatch, s3_client, project, capsys):
    _write_gated(project)
    project.build(writers=GATED)
    _main_on_dbt(monkeypatch, s3_client, project, {"nynjtc_trail_alerts": HELD, "ourhike_closures": PASSED})

    with pytest.raises(SystemExit, match="conditions/nynjtc_alerts.json"):
        publish.main()

    published = _keys(s3_client)
    assert "stewards.json" in published and "conditions/closures.json" in published
    assert "conditions/nynjtc_alerts.json" not in published
    out = capsys.readouterr().out
    assert f"::error title=conditions/nynjtc_alerts.json not rewritten::nynjtc_trail_alerts is held: {HELD.held_because}" in out


def test_main_after_a_partial_build_publishes_what_was_written_and_keeps_the_failed_writers_key(
    monkeypatch, s3_client, project, capsys
):
    """publish-conditions.yml sets OURHIKE_BUILD_PARTIAL when build_marts.py exited PARTIAL_EXIT; its last step,
    not publish.py, turns the run red."""
    _write_gated(project)
    project.write("conditions_nynjtc_alerts.json", '{"nynjtc_alerts": [')
    project.build(writers=GATED)
    _fail(project, writers={"model.ourhike.pub_conditions_nynjtc_alerts": "error"})
    _main_on_dbt(monkeypatch, s3_client, project, {"nynjtc_trail_alerts": PASSED, "ourhike_closures": PASSED})
    monkeypatch.setenv(publish.BUILD_PARTIAL_ENV_VAR, "true")

    result = publish.main()

    published = _keys(s3_client)
    assert result["version_written"] is True
    assert "stewards.json" in published and "conditions/closures.json" in published
    assert "conditions/nynjtc_alerts.json" not in published
    assert "KEPT: conditions/nynjtc_alerts.json carries the bucket's last good file forward" in capsys.readouterr().out


def test_main_fails_for_a_held_file_when_nothing_else_changed(monkeypatch, s3_client, project):
    """The quiet path, every writer kept, still ends red for a held source."""
    writers = {"model.ourhike.pub_conditions_nynjtc_alerts": GATED["model.ourhike.pub_conditions_nynjtc_alerts"]}
    project.build(writers=writers)
    _main_on_dbt(monkeypatch, s3_client, project, {"nynjtc_trail_alerts": HELD})

    with pytest.raises(SystemExit, match="held back by int_closures__gate"):
        publish.main()

    assert _keys(s3_client) == {}


def test_main_does_not_fail_for_an_unreviewed_file(monkeypatch, s3_client, project):
    _write_gated(project)
    project.build(writers=GATED)
    unreviewed = publish.GateVerdict("nobody has reviewed it", awaiting_review=True)
    _main_on_dbt(monkeypatch, s3_client, project, {"nynjtc_trail_alerts": unreviewed, "ourhike_closures": PASSED})

    result = publish.main()

    assert result["version_written"] is True


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
