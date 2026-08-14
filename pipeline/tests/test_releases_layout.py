"""Tests for the `releases/` tree - the immutable folder per dated release.

R2_LAYOUT.md declared this prefix and lib/r2_keys.py has enforced its shape
since it was written. Nothing wrote it (#500): measured against the live bucket
on 2026-08-09, `releases/index.json` was a 404 while `latest.json` was a 206.

Two halves, tested in two ways. `lib/releases.py` is arithmetic over ids and an
index, so it is tested directly. What `publish.py` does with it runs against
moto - a real S3 implementation, which matters more here than usual because the
whole affordability argument rests on `copy_object` being a server-side copy
rather than a download and a re-upload, and a hand-written stub would let that
be wrong while passing.

What most of this file is actually about is the two ways a release folder can
be worse than useless:

  - **Incomplete.** A folder holding only what changed this week makes
    correctness depend on chasing a chain backwards, and one gap in that chain
    is a 404 on a mountain. So the tests below care more about the artifacts
    this run did NOT upload than about the ones it did.
  - **Advertised before it exists.** `latest.json` is what every client fetches
    first. A pointer naming a release folder that is not there yet is exactly
    the state the rollback story assumes cannot happen.
"""

import json
from datetime import date

import boto3
import pytest
from moto import mock_aws

import publish
from lib import data_env, releases

BUCKET = "ourhike-releases-test"


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
    trails = tmp_path / "trails.geojson"
    trails.write_text('{"type": "FeatureCollection", "features": []}')
    shelters = tmp_path / "poi_shelter.geojson"
    shelters.write_text('{"type": "FeatureCollection", "features": [{"id": 1}]}')
    return {
        "trails.geojson": {"path": str(trails), "sha256": publish.sha256_file(trails)},
        "poi_shelter.geojson": {"path": str(shelters), "sha256": publish.sha256_file(shelters)},
    }


def keys_under(s3_client, prefix):
    response = s3_client.list_objects_v2(Bucket=BUCKET, Prefix=prefix)
    return sorted(item["Key"] for item in response.get("Contents", []))


def read_json(s3_client, key):
    return json.loads(s3_client.get_object(Bucket=BUCKET, Key=key)["Body"].read())


# --- the ids and the index, without a bucket -------------------------------


def test_a_release_is_named_for_the_day_it_was_published():
    assert releases.next_release_id([], today=date(2026, 8, 13)) == "2026-08-13"


def test_a_second_release_on_one_day_does_not_overwrite_the_first():
    """The case R2_LAYOUT.md's `-2` suffix exists for. Without this a morning
    release and an afternoon one are the same folder, and the folder is
    supposed to be the thing that never changes."""
    assert releases.next_release_id(["2026-08-13"], today=date(2026, 8, 13)) == "2026-08-13-2"


def test_the_suffix_keeps_counting_past_the_second():
    taken = ["2026-08-13", "2026-08-13-2", "2026-08-13-3"]

    assert releases.next_release_id(taken, today=date(2026, 8, 13)) == "2026-08-13-4"


def test_the_first_release_of_a_day_is_unsuffixed_rather_than_dash_one():
    """`2026-08-13` and `2026-08-13-1` would be two spellings of "the first one
    today", and the layout cannot rename either afterwards."""
    assert releases.next_release_id(["2026-08-12-2"], today=date(2026, 8, 13)) == "2026-08-13"


@pytest.mark.parametrize("index", [None, {}, {"releases": "not a list"}, {"releases": [{"no": "id"}]}])
def test_an_absent_or_malformed_index_reads_as_no_releases(index):
    """The first publish has no index at all, and that is indistinguishable
    from a corrupt one at this level. Both mean no ids are taken; the cost of
    being wrong is a colliding id that r2_keys then rejects."""
    assert releases.index_ids(index) == []


def test_the_index_entry_carries_the_date_the_prune_rule_needs():
    """DATA_RELEASES.md's rule - 90 days after being SUPERSEDED, floor of the
    three most recent - cannot evaluate either half without a date. And
    supersession is derivable from this list precisely because entries are
    appended in order: a release is superseded when the next one is created.

    An entry carrying only an id would be an index a prune job could not use,
    and R2_LAYOUT.md warns that a prefix whose rule cannot be evaluated is one
    a prune job may delete."""
    index = releases.append_release(None, release_id="2026-08-13", version="v1", created_at="2026-08-13T03:00:00+00:00")

    [entry] = index["releases"]
    assert entry["id"] == "2026-08-13"
    assert entry["created_at"] == "2026-08-13T03:00:00+00:00"
    assert entry["version"] == "v1"


def test_appending_keeps_every_release_already_listed():
    first = releases.append_release(None, release_id="2026-08-12", version="v1", created_at="a")

    second = releases.append_release(first, release_id="2026-08-13", version="v2", created_at="b")

    assert [entry["id"] for entry in second["releases"]] == ["2026-08-12", "2026-08-13"]


@pytest.mark.parametrize(
    "name,included",
    [
        ("trails.geojson", True),
        ("poi_water.geojson", True),
        ("background.pmtiles", True),
        ("build_state.json", True),
        ("conditions/closures.json", False),
        ("conditions/reports.json", False),
    ],
)
def test_conditions_are_the_one_thing_a_release_folder_may_not_hold(name, included):
    """A closure that has reopened must stop being served, and an immutable
    folder cannot express that - it could only add a second answer beside the
    first. Everything else is in by default, which is the safe direction: a
    wrong inclusion costs a duplicate copy, a wrong exclusion costs
    completeness."""
    assert releases.is_release_artifact(name) is included


# --- what a publish actually writes ----------------------------------------


def test_publishing_writes_a_release_folder_and_lists_it(s3_client, artifacts):
    result = publish.publish(artifacts, s3_client=s3_client, bucket=BUCKET)

    release_id = result["release"]
    assert keys_under(s3_client, f"releases/{release_id}/") == sorted(
        [
            f"releases/{release_id}/manifest.json",
            f"releases/{release_id}/poi_shelter.geojson",
            f"releases/{release_id}/trails.geojson",
        ]
    )
    assert releases.index_ids(read_json(s3_client, releases.RELEASE_INDEX_KEY)) == [release_id]


def test_the_release_folder_holds_the_same_bytes_as_the_flat_key(s3_client, artifacts):
    """The copy is server-side, so this is really asking whether the right
    source key was named - a `copy_object` from the wrong place succeeds just
    as happily as from the right one."""
    result = publish.publish(artifacts, s3_client=s3_client, bucket=BUCKET)

    flat = s3_client.get_object(Bucket=BUCKET, Key="trails.geojson")["Body"].read()
    staged = s3_client.get_object(Bucket=BUCKET, Key=f"releases/{result['release']}/trails.geojson")["Body"].read()
    assert staged == flat


def test_the_pointer_names_the_release_that_holds_its_bytes(s3_client, artifacts):
    result = publish.publish(artifacts, s3_client=s3_client, bucket=BUCKET)

    assert read_json(s3_client, "latest.json")["release"] == result["release"]


def test_the_pointer_keeps_describing_the_flat_keys_it_always_did(s3_client, artifacts):
    """Additive, not a replacement. Every build already in the field reads
    `artifacts` and fetches flat keys, and a folder layout is not a reason to
    break a phone that already has an archive."""
    publish.publish(artifacts, s3_client=s3_client, bucket=BUCKET)

    manifest = read_json(s3_client, "latest.json")
    assert set(manifest["artifacts"]) == {"trails.geojson", "poi_shelter.geojson"}
    assert keys_under(s3_client, "trails.geojson") == ["trails.geojson"]


def test_a_release_folder_is_complete_even_when_one_artifact_changed(s3_client, artifacts, tmp_path):
    """THE property. The second publish uploads one artifact and skips the
    other; both have to be in the new folder, or a client resolving it finds a
    404 for the one that did not change that week."""
    publish.publish(artifacts, s3_client=s3_client, bucket=BUCKET)

    changed = tmp_path / "trails.geojson"
    changed.write_text('{"type": "FeatureCollection", "features": [{"id": 99}]}')
    second = publish.publish(
        {**artifacts, "trails.geojson": {"path": str(changed), "sha256": publish.sha256_file(changed)}},
        s3_client=s3_client,
        bucket=BUCKET,
    )

    assert second["uploaded"] == ["trails.geojson"]
    assert second["skipped"] == ["poi_shelter.geojson"]
    assert set(second["release_artifacts"]) == {"trails.geojson", "poi_shelter.geojson"}


def test_a_release_folder_carries_forward_an_artifact_this_checkout_never_built(s3_client, artifacts, tmp_path):
    """A partial checkout - one that ran export_trails.py and nothing else -
    still publishes, and publish()'s manifest merge keeps the artifacts it did
    not produce. Those are in the bucket and belong in the folder, so the
    folder is built from the MERGED manifest rather than from what was
    collected locally."""
    publish.publish(artifacts, s3_client=s3_client, bucket=BUCKET)

    only_trails = tmp_path / "trails2.geojson"
    only_trails.write_text('{"type": "FeatureCollection", "features": [{"id": 7}]}')
    second = publish.publish(
        {"trails.geojson": {"path": str(only_trails), "sha256": publish.sha256_file(only_trails)}},
        s3_client=s3_client,
        bucket=BUCKET,
    )

    assert "poi_shelter.geojson" in second["release_artifacts"]
    assert f"releases/{second['release']}/poi_shelter.geojson" in keys_under(s3_client, f"releases/{second['release']}/")


def test_conditions_reach_the_flat_key_and_never_the_release_folder(s3_client, artifacts, tmp_path):
    closures = tmp_path / "closures.json"
    closures.write_text('{"closures": []}')

    result = publish.publish(
        {**artifacts, "conditions/closures.json": {"path": str(closures), "sha256": publish.sha256_file(closures)}},
        s3_client=s3_client,
        bucket=BUCKET,
    )

    assert keys_under(s3_client, "conditions/") == ["conditions/closures.json"]
    assert "conditions/closures.json" not in result["release_artifacts"]
    assert f"releases/{result['release']}/conditions/closures.json" not in keys_under(s3_client, f"releases/{result['release']}/")


def test_the_release_manifest_describes_the_folder_it_sits_in(s3_client, artifacts, tmp_path):
    """Self-describing on purpose: resolving a release should be one fetch,
    rather than a lookup in the index plus the pointer that used to describe
    it. So the manifest inside the folder must not list what the folder
    excludes."""
    closures = tmp_path / "closures.json"
    closures.write_text('{"closures": []}')

    result = publish.publish(
        {**artifacts, "conditions/closures.json": {"path": str(closures), "sha256": publish.sha256_file(closures)}},
        s3_client=s3_client,
        bucket=BUCKET,
    )

    manifest = read_json(s3_client, f"releases/{result['release']}/manifest.json")
    assert set(manifest["artifacts"]) == {"trails.geojson", "poi_shelter.geojson"}
    assert manifest["release"] == result["release"]


def test_a_sidecar_travels_into_the_release_folder(s3_client, artifacts, tmp_path):
    """build_state.json records the upstream markers this release was built
    from. In the folder, a release can be asked what it was built from years
    later; at the flat key only the newest answer survives."""
    state = tmp_path / "build_state.json"
    state.write_text('{"version": 1}')

    result = publish.publish(
        artifacts,
        sidecars={"build_state.json": {"path": str(state), "sha256": publish.sha256_file(state)}},
        s3_client=s3_client,
        bucket=BUCKET,
    )

    assert "build_state.json" in result["release_artifacts"]


def test_a_publish_that_changes_nothing_writes_no_release(s3_client, artifacts):
    """The rule publish() already held for versions, extended to folders. A
    no-op release would burn 1.6 GB of storage and push a real release out of
    the retention window for nothing."""
    first = publish.publish(artifacts, s3_client=s3_client, bucket=BUCKET)

    second = publish.publish(artifacts, s3_client=s3_client, bucket=BUCKET)

    assert second["version_written"] is False
    assert releases.index_ids(read_json(s3_client, releases.RELEASE_INDEX_KEY)) == [first["release"]]


def test_a_conditions_only_change_moves_the_pointer_and_freezes_nothing(s3_client, artifacts, tmp_path):
    """The daily bake stamps generated_at into its bytes, so its sha moves
    even when no closure changed - which means publish() cannot rely on "no
    uploads" alone to skip the folder. Before #646, every daily conditions
    run therefore copied every frozen artifact into a new byte-identical
    folder: one per environment per day, an index entry per day, and no
    prune job anywhere. A run whose only uploads are excluded names now
    freezes nothing - the pointer still moves, and keeps naming the last
    real release, because those are still the bytes the folders hold."""
    first = publish.publish(artifacts, s3_client=s3_client, bucket=BUCKET)
    folders_before = keys_under(s3_client, "releases/")

    closures = tmp_path / "closures.json"
    closures.write_text('{"closures": [], "generated_at": "2026-08-13T08:40:00+00:00"}')
    second = publish.publish(
        {**artifacts, "conditions/closures.json": {"path": str(closures), "sha256": publish.sha256_file(closures)}},
        s3_client=s3_client,
        bucket=BUCKET,
    )

    # The pointer moved - fresh conditions hashes are the point of the bake -
    assert second["version_written"] is True
    pointer = read_json(s3_client, "latest.json")
    assert pointer["version"] == second["version"]
    assert pointer["artifacts"]["conditions/closures.json"] == {"sha256": publish.sha256_file(closures)}
    # - and nothing was frozen: no new folder, no new index entry, and the
    # pointer keeps naming the release whose folders hold these bytes.
    assert second["release"] == first["release"]
    assert second["release_artifacts"] == []
    assert pointer["release"] == first["release"]
    assert releases.index_ids(read_json(s3_client, releases.RELEASE_INDEX_KEY)) == [first["release"]]
    assert keys_under(s3_client, "releases/") == folders_before


def test_two_publishes_on_one_day_get_two_folders(s3_client, artifacts, tmp_path):
    first = publish.publish(artifacts, s3_client=s3_client, bucket=BUCKET)

    changed = tmp_path / "trails.geojson"
    changed.write_text('{"type": "FeatureCollection", "features": [{"id": 42}]}')
    second = publish.publish(
        {**artifacts, "trails.geojson": {"path": str(changed), "sha256": publish.sha256_file(changed)}},
        s3_client=s3_client,
        bucket=BUCKET,
    )

    assert second["release"] != first["release"]
    assert releases.index_ids(read_json(s3_client, releases.RELEASE_INDEX_KEY)) == [
        first["release"],
        second["release"],
    ]


def test_an_earlier_release_is_never_rewritten(s3_client, artifacts, tmp_path):
    """Immutable is the whole point: it is what a rollback goes back to and
    what a phone pinned to an older release keeps reading."""
    first = publish.publish(artifacts, s3_client=s3_client, bucket=BUCKET)
    before = s3_client.get_object(Bucket=BUCKET, Key=f"releases/{first['release']}/trails.geojson")["Body"].read()

    changed = tmp_path / "trails.geojson"
    changed.write_text('{"type": "FeatureCollection", "features": [{"id": 42}]}')
    publish.publish(
        {**artifacts, "trails.geojson": {"path": str(changed), "sha256": publish.sha256_file(changed)}},
        s3_client=s3_client,
        bucket=BUCKET,
    )

    after = s3_client.get_object(Bucket=BUCKET, Key=f"releases/{first['release']}/trails.geojson")["Body"].read()
    assert after == before


def test_the_pointer_is_not_moved_when_the_release_folder_cannot_be_written(s3_client, artifacts, monkeypatch):
    """The ordering, asserted by breaking it. `latest.json` is what every
    client fetches first, so a pointer naming a folder that is not there is
    the one state the rollback story assumes cannot happen - and it is
    invisible until somebody tries to roll back.
    """
    publish.publish(artifacts, s3_client=s3_client, bucket=BUCKET)
    settled = read_json(s3_client, "latest.json")["version"]

    def refuse(*args, **kwargs):
        raise RuntimeError("copy failed")

    monkeypatch.setattr(s3_client, "copy_object", refuse)
    changed_artifacts = {**artifacts, "trails.geojson": {**artifacts["trails.geojson"], "sha256": "different"}}

    with pytest.raises(RuntimeError):
        publish.publish(changed_artifacts, s3_client=s3_client, bucket=BUCKET)

    assert read_json(s3_client, "latest.json")["version"] == settled


def test_a_release_folder_is_staged_under_the_environment_that_published_it(s3_client, artifacts, monkeypatch):
    """UA's tree is this whole layout again under `environments/ua/`. A
    release that landed at the root from a UA run would be production data
    written by a rehearsal."""
    monkeypatch.setenv(data_env.ENVIRONMENT_VAR, "ua")

    result = publish.publish(artifacts, s3_client=s3_client, bucket=BUCKET)

    assert keys_under(s3_client, f"environments/ua/releases/{result['release']}/")
    assert keys_under(s3_client, "releases/") == []
