"""Tests for publish.py - change-aware sync of Export's artifacts to R2.

See TECHNICAL_ARCHITECTURE.md's "Publish, change-aware end to end" section:
only artifacts whose hash actually changed get uploaded, and no new
manifest version is ever written if nothing changed - not even a no-op
version bump. Real network/S3 calls are never allowed in the suite (this
project's established convention, same as requests-mock elsewhere) - moto
mocks S3/R2 (R2 is S3-compatible) instead of hitting a real bucket.
"""

import gzip
import json
import pathlib
import re

import boto3
import pytest
from moto import mock_aws

import publish
from lib import data_env
from lib.photo_store import PHOTOS_DIRNAME, photo_digest, photo_key

BUCKET = "ourhike-test-bucket"


@pytest.fixture(autouse=True)
def enable_r2_writes(monkeypatch):
    """Both gates publish.py checks, turned on for the tests that are not about
    the gates themselves.

    The environment is `production` because that is what most of this file
    asserts about - root keys, `latest.json` at the bucket root - and naming it
    keeps those assertions true statements about production rather than about
    whichever environment happened to be set. The refusals themselves are
    tested where they belong, below and in test_data_env.py.
    """
    monkeypatch.setenv(publish.WRITE_ENABLED_ENV_VAR, "true")
    monkeypatch.setenv(data_env.ENVIRONMENT_VAR, data_env.PRODUCTION)


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


def test_publish_refuses_a_file_that_changed_after_its_hash_was_recorded(s3_client, local_artifacts, tmp_path):
    """#659: most collected hashes are copied from exporter manifests, and
    nothing between that write and the upload re-checked them. A file
    rebuilt after its manifest was recorded would upload fresh bytes under
    a stale hash - which every hash-verifying client then rejects - or
    skip a changed file whose stale hash still matches the bucket. The
    publish must fail before the first upload, naming the artifact."""
    (tmp_path / "trails.geojson").write_text('{"type": "FeatureCollection", "features": [{"id": "rebuilt"}]}')

    with pytest.raises(RuntimeError, match="trails.geojson"):
        publish.publish(local_artifacts, s3_client=s3_client, bucket=BUCKET)

    # Nothing may have landed - the failed run must not half-publish.
    listed = s3_client.list_objects_v2(Bucket=BUCKET)
    assert listed.get("KeyCount", 0) == 0


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
    assert set(publish.BACKGROUND_ARCHIVES) - {"light", "standard", "fine"} == {"quad_sheet"}


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


def test_collect_gathers_published_conditions_under_their_own_prefix(tmp_path, monkeypatch):
    """features/CONDITIONS_DELIVERY.md. Ordinary artifacts so they get the
    same sha256 diffing as everything else - which is what makes a daily bake
    cheap, since a day with no condition changes uploads nothing at all."""
    monkeypatch.setattr(publish, "PROCESSED_DIR", tmp_path)
    conditions_dir = tmp_path / "conditions"
    conditions_dir.mkdir()
    closures = conditions_dir / "closures.json"
    closures.write_text('{"generated_at": "2026-08-08T06:00:00Z", "closures": []}')
    reports = conditions_dir / "reports.json"
    reports.write_text('{"generated_at": "2026-08-08T06:00:00Z", "reports": []}')
    (tmp_path / "conditions_manifest.json").write_text(
        json.dumps(
            {
                "artifacts": {
                    "closures": {"path": str(closures), "sha256": "abc123", "count": 0},
                    "reports": {"path": str(reports), "sha256": "def456", "count": 0},
                }
            }
        )
    )

    artifacts = publish.collect_artifacts()

    # The keys are the prefixed ones, not bare names at the root - a key in
    # this bucket can never be renamed, only abandoned in place.
    assert artifacts["conditions/closures.json"]["sha256"] == "abc123"
    assert artifacts["conditions/reports.json"]["sha256"] == "def456"


def test_collect_ignores_conditions_that_have_not_been_exported(tmp_path, monkeypatch):
    """The normal state until the reader credential exists. An absent bake is
    an absence, not an error - same rule as a background tier."""
    monkeypatch.setattr(publish, "PROCESSED_DIR", tmp_path)

    collected = publish.collect_artifacts()
    assert "conditions/closures.json" not in collected
    assert "conditions/reports.json" not in collected


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


# --- The hiking sheet's offline archives (#184/#186) -----------------------
#
# The vector basemap package and the DEM are the default background sheet's
# two downloads - distinct packages a hiker takes both of, not detail tiers
# of one sheet, which is why they live in their own mapping rather than in
# BACKGROUND_ARCHIVES.


def test_offline_sheet_archives_are_the_basemap_cuts_and_the_dem():
    """The names are pinned, not just the set: they are the flat R2 keys the
    client requests (packages.ts sources, dataManifest hash lookups), and
    publish()'s additive-only manifest merge means a renamed key is a new
    key forever - the old one can never be removed by this module."""
    assert publish.OFFLINE_SHEET_ARCHIVES == {
        "basemap": "at_basemap_package.pmtiles",
        "basemap_z13": "at_basemap_package_z13.pmtiles",
        "dem": "dem.pmtiles",
    }


def test_offline_sheet_archives_do_not_collide_with_the_raster_tiers():
    tier_names = set(publish.BACKGROUND_ARCHIVES.values())
    sheet_names = set(publish.OFFLINE_SHEET_ARCHIVES.values())

    assert tier_names.isdisjoint(sheet_names)


def test_collect_gathers_offline_sheet_archives_that_exist(tmp_path, monkeypatch):
    monkeypatch.setattr(publish, "PROCESSED_DIR", tmp_path)
    for name in publish.OFFLINE_SHEET_ARCHIVES.values():
        (tmp_path / name).write_bytes(b"fake pmtiles bytes for " + name.encode())

    artifacts = publish.collect_artifacts()

    for name in publish.OFFLINE_SHEET_ARCHIVES.values():
        assert name in artifacts
        assert artifacts[name]["sha256"] == publish.sha256_file(tmp_path / name)


def test_collect_skips_an_offline_sheet_archive_not_built_this_run(tmp_path, monkeypatch):
    """The DEM workflow's runner holds only dem.pmtiles; the basemap
    workflow's only its package. Each publishes what it has, and the
    manifest merge keeps the other's live entry untouched."""
    monkeypatch.setattr(publish, "PROCESSED_DIR", tmp_path)
    (tmp_path / publish.OFFLINE_SHEET_ARCHIVES["dem"]).write_bytes(b"only the dem")

    artifacts = publish.collect_artifacts()

    assert publish.OFFLINE_SHEET_ARCHIVES["dem"] in artifacts
    assert publish.OFFLINE_SHEET_ARCHIVES["basemap"] not in artifacts


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


def test_collect_sidecars_reads_each_file_from_its_own_shelf(tmp_path, monkeypatch):
    """build_state.json is processed build metadata; the two photo outcome
    files are fetch products living in raw/ (#465). A collector that looked
    on one shelf for the other's file would silently publish nothing."""
    processed, raw = tmp_path / "processed", tmp_path / "raw"
    processed.mkdir(), raw.mkdir()
    monkeypatch.setattr(publish, "PROCESSED_DIR", processed)
    monkeypatch.setattr(publish, "RAW_DIR", raw)
    (processed / "build_state.json").write_text("{}")
    (raw / "poi_images_atc.json").write_text('{"pois": {}}')
    (raw / "poi_images.json").write_text('{"pois": {}}')

    assert set(publish.collect_sidecars()) == {"build_state.json", "poi_images_atc.json", "poi_images.json"}


def test_collect_sidecars_is_empty_when_nothing_was_written(tmp_path, monkeypatch):
    monkeypatch.setattr(publish, "PROCESSED_DIR", tmp_path)
    monkeypatch.setattr(publish, "RAW_DIR", tmp_path)

    assert publish.collect_sidecars() == {}


# --- POI photos (#362) ---
#
# Photos deliberately sit outside the manifest: content-addressed keys already
# carry the checksum a manifest entry would restate, and several thousand of
# them would add hundreds of KB to the file every client fetches first.


@pytest.fixture
def local_photos(tmp_path):
    """Two cached photos, named the way lib/photo_store.py names them."""
    photos_dir = tmp_path / PHOTOS_DIRNAME
    photos_dir.mkdir()
    keys = {}
    for content in (b"\xff\xd8 shelter", b"\xff\xd8 spring"):
        digest = photo_digest(content)
        path = photos_dir / f"{digest}.jpg"
        path.write_bytes(content)
        keys[photo_key(digest)] = str(path)
    return keys


def test_photos_are_uploaded_under_their_content_addressed_keys(s3_client, local_artifacts, local_photos):
    result = publish.publish(local_artifacts, sidecars={}, photos=local_photos, s3_client=s3_client, bucket=BUCKET)

    assert sorted(result["photos_uploaded"]) == sorted(local_photos)
    for key, path in local_photos.items():
        stored = s3_client.get_object(Bucket=BUCKET, Key=key)["Body"].read()
        assert stored == open(path, "rb").read()


def test_a_photo_already_in_the_bucket_is_not_re_uploaded(s3_client, local_artifacts, local_photos):
    """The key IS the hash, so an object already at that key is by
    construction the bytes we were about to send. Re-uploading thousands of
    unchanged photos every run is the cost this check exists to avoid."""
    publish.publish(local_artifacts, sidecars={}, photos=local_photos, s3_client=s3_client, bucket=BUCKET)

    again = publish.publish(local_artifacts, sidecars={}, photos=local_photos, s3_client=s3_client, bucket=BUCKET)

    assert again["photos_uploaded"] == []


def test_photos_land_before_the_manifest_that_makes_them_reachable(s3_client, local_artifacts, local_photos):
    """Ordering is the only thing keeping this safe, since photos are outside
    the manifest and cannot be diffed into the same transaction as the
    artifacts. A manifest live while its photos are still uploading is a card
    pointing at a 404."""
    seen: list[str] = []
    real_upload, real_put = s3_client.upload_file, s3_client.put_object

    def record_upload(path, bucket, key, **kwargs):
        seen.append(key)
        return real_upload(path, bucket, key, **kwargs)

    def record_put(**kwargs):
        seen.append(kwargs["Key"])
        return real_put(**kwargs)

    s3_client.upload_file, s3_client.put_object = record_upload, record_put

    publish.publish(local_artifacts, sidecars={}, photos=local_photos, s3_client=s3_client, bucket=BUCKET)

    photo_positions = [i for i, key in enumerate(seen) if key.startswith("photos/")]
    assert photo_positions, "no photo was uploaded at all"
    assert max(photo_positions) < seen.index(publish.MANIFEST_KEY)
    # And before the artifacts that name them, not merely before the manifest.
    assert max(photo_positions) < seen.index("trails.geojson")


def test_collect_photos_leaves_face_gate_held_bytes_out_of_the_upload_set(tmp_path, monkeypatch):
    """The bucket half of the #836 gate. An unreferenced object is not a
    private one - the digests travel in the published outcome sidecars - so
    a flagged-undecided or refused photo must not be uploaded at all, while
    everything screened-clear or cleared still is."""
    photos_dir = tmp_path / PHOTOS_DIRNAME
    photos_dir.mkdir()
    digests = {}
    for name, content in (("clean", b"\xff\xd8 shelter"), ("held", b"\xff\xd8 group shot"), ("refused", b"\xff\xd8 refused")):
        digest = photo_digest(content)
        (photos_dir / f"{digest}.jpg").write_bytes(content)
        digests[name] = digest
    (tmp_path / "poi_images.json").write_text(
        json.dumps(
            {
                "pois": {
                    "a": {"status": "found", "photo": {"digest": digests["clean"], "screen": {"faces": 0}}},
                    "b": {"status": "found", "photo": {"digest": digests["held"], "screen": {"faces": 2}}},
                    "c": {"status": "found", "photo": {"digest": digests["refused"], "screen": {"faces": 0}}},
                }
            }
        )
    )
    monkeypatch.setattr(publish, "RAW_DIR", tmp_path)
    monkeypatch.setattr(publish, "load_decisions", lambda: {digests["refused"]: {"decision": "refused", "on": "2026-08-20"}})

    collected = publish.collect_photos()

    assert photo_key(digests["clean"]) in collected
    assert photo_key(digests["held"]) not in collected
    assert photo_key(digests["refused"]) not in collected


def test_photos_alone_do_not_write_a_new_version(s3_client, local_artifacts, local_photos):
    """A photo only becomes visible through a poi artifact that references
    it; that artifact's bytes changing is the real event. Bumping the version
    for a photo would be the no-op bump publish() exists to prevent."""
    publish.publish(local_artifacts, sidecars={}, photos={}, s3_client=s3_client, bucket=BUCKET)

    result = publish.publish(local_artifacts, sidecars={}, photos=local_photos, s3_client=s3_client, bucket=BUCKET)

    assert result["photos_uploaded"]  # they did upload
    assert result["version_written"] is False  # and wrote no version
    assert publish.MANIFEST_KEY not in result["uploaded"]


# --- #465: every photo promise is settled against the bucket ---
#
# The fetches stopped requiring local bytes (a record with digests vouches for
# itself), so THIS is now the only thing standing between a stale outcome file
# and a card resolving to a 404 on a mountain.


def _poi_artifact(tmp_path, properties_list):
    path = tmp_path / "poi_shelters.geojson"
    features = [{"type": "Feature", "properties": props, "geometry": None} for props in properties_list]
    path.write_text(json.dumps({"type": "FeatureCollection", "features": features}))
    return {"poi_shelters.geojson": {"path": str(path), "sha256": publish.sha256_file(path)}}


def test_referenced_photo_keys_reads_the_card_key_and_the_gallery(tmp_path):
    """Both places an artifact promises a photo: the card's photo_key and the
    gallery's JSON-encoded list. Missing the gallery would let its later
    slots 404 while the check reported clean."""
    artifacts = _poi_artifact(
        tmp_path,
        [
            {"photo_key": "photos/aaa.jpg", "photos": json.dumps([{"key": "photos/aaa.jpg"}, {"key": "photos/bbb.jpg"}])},
            {"name": "no photo here"},
        ],
    )

    assert publish.referenced_photo_keys(artifacts) == {"photos/aaa.jpg", "photos/bbb.jpg"}


def test_referenced_photo_keys_ignores_artifacts_that_are_not_poi_layers(tmp_path):
    path = tmp_path / "trails.geojson"
    path.write_text(json.dumps({"type": "FeatureCollection", "features": [{"properties": {"photo_key": "photos/x.jpg"}}]}))

    keys = publish.referenced_photo_keys({"trails.geojson": {"path": str(path), "sha256": "irrelevant"}})

    assert keys == set()


def test_a_promise_backed_by_the_bucket_passes_without_local_bytes(s3_client, local_artifacts, tmp_path):
    """The whole point of #465: a cold machine whose data/ tree is empty can
    still publish, because the corpus is already content-addressed in the
    bucket and a HEAD per referenced key proves it."""
    s3_client.put_object(Bucket=BUCKET, Key="photos/aaa.jpg", Body=b"\xff\xd8 already there")
    artifacts = {**local_artifacts, **_poi_artifact(tmp_path, [{"photo_key": "photos/aaa.jpg"}])}

    result = publish.publish(artifacts, sidecars={}, photos={}, s3_client=s3_client, bucket=BUCKET)

    assert result["version_written"] is True


def test_a_promise_backed_by_nothing_fails_the_publish_before_any_artifact_lands(s3_client, local_artifacts, tmp_path):
    """A stale outcome record promising a photo nobody ever uploaded must
    fail HERE, loudly, before the manifest can make the promise reachable."""
    artifacts = {**local_artifacts, **_poi_artifact(tmp_path, [{"photo_key": "photos/never-uploaded.jpg"}])}

    with pytest.raises(RuntimeError, match="never-uploaded"):
        publish.publish(artifacts, sidecars={}, photos={}, s3_client=s3_client, bucket=BUCKET)

    with pytest.raises(s3_client.exceptions.NoSuchKey):
        s3_client.get_object(Bucket=BUCKET, Key=publish.MANIFEST_KEY)


def test_a_promise_backed_by_the_local_store_passes_without_a_head_request(s3_client, local_artifacts, local_photos, tmp_path):
    """A key in the local store was just settled by upload_photos - HEADing
    it again would double the request count for the common case."""
    key = next(iter(local_photos))
    artifacts = {**local_artifacts, **_poi_artifact(tmp_path, [{"photo_key": key}])}

    result = publish.publish(artifacts, sidecars={}, photos=local_photos, s3_client=s3_client, bucket=BUCKET)

    assert result["version_written"] is True


def test_an_illegal_photo_key_fails_the_run_before_anything_uploads(s3_client, local_artifacts, tmp_path):
    """Same gate the artifacts get: a key that breaks the layout must fail
    the whole run rather than leave half a set in the bucket."""
    stray = tmp_path / "Photo_V2.jpg"
    stray.write_bytes(b"\xff\xd8")

    with pytest.raises(ValueError):
        publish.publish(
            local_artifacts,
            sidecars={},
            photos={"photos/Photo_V2.jpg": str(stray)},
            s3_client=s3_client,
            bucket=BUCKET,
        )

    assert "Contents" not in s3_client.list_objects_v2(Bucket=BUCKET)


def test_a_successful_publish_does_not_also_report_that_nothing_changed(
    monkeypatch, capsys, s3_client, local_artifacts, tmp_path
):
    """The log is the only signal a scheduled publish gives.

    `main()`'s "Nothing changed" branch used to hang off the *photos* check, so
    a run that wrote a version and uploaded no photos printed both "Published
    version <id>" and "Nothing changed ... No new version written". The first
    real publish-conditions.yml run did exactly that (2026-08-08) - and on a
    job whose purpose is getting safety data to a hiker, a log claiming it did
    nothing sends somebody hunting a fault that is not there.
    """
    monkeypatch.setattr(publish, "collect_artifacts", lambda: local_artifacts)
    monkeypatch.setattr(publish, "collect_sidecars", dict)
    monkeypatch.setattr(publish, "collect_photos", dict)
    monkeypatch.setattr(publish.boto3, "client", lambda *a, **k: s3_client)
    # All four, not just the bucket: `publish()` reads the other three while
    # *building* the boto3 call's arguments, so they are needed even though
    # the stub above ignores every one of them.
    monkeypatch.setenv("R2_BUCKET", BUCKET)
    monkeypatch.setenv("R2_ENDPOINT_URL", "https://unused.invalid")
    monkeypatch.setenv("R2_ACCESS_KEY_ID", "unused")
    monkeypatch.setenv("R2_SECRET_ACCESS_KEY", "unused")

    publish.main()

    out = capsys.readouterr().out
    assert "Published version" in out
    assert "Nothing changed" not in out


def test_a_run_with_nothing_to_do_still_says_so(monkeypatch, capsys, s3_client, local_artifacts):
    """The other half: the message has to survive, or a genuinely idle run
    prints nothing at all and reads as a job that did not run."""
    monkeypatch.setattr(publish, "collect_artifacts", lambda: local_artifacts)
    monkeypatch.setattr(publish, "collect_sidecars", dict)
    monkeypatch.setattr(publish, "collect_photos", dict)
    monkeypatch.setattr(publish.boto3, "client", lambda *a, **k: s3_client)
    # All four, not just the bucket: `publish()` reads the other three while
    # *building* the boto3 call's arguments, so they are needed even though
    # the stub above ignores every one of them.
    monkeypatch.setenv("R2_BUCKET", BUCKET)
    monkeypatch.setenv("R2_ENDPOINT_URL", "https://unused.invalid")
    monkeypatch.setenv("R2_ACCESS_KEY_ID", "unused")
    monkeypatch.setenv("R2_SECRET_ACCESS_KEY", "unused")

    publish.main()  # first run publishes
    capsys.readouterr()
    publish.main()  # second run has nothing to do

    out = capsys.readouterr().out
    assert "Nothing changed" in out
    assert "Published version" not in out


# ---------------------------------------------------------------------------
# Which environment a publish lands in (features/DATA_ENVIRONMENTS.md).
#
# The property under test throughout is the one the feature exists for: a run
# publishing to UA writes nothing production reads. It is asserted by listing
# the bucket rather than by inspecting the call arguments, because "what is in
# the bucket afterwards" is the only version of that claim a hiker experiences.
# ---------------------------------------------------------------------------


def _keys_in(s3_client):
    listing = s3_client.list_objects_v2(Bucket=BUCKET)
    return sorted(item["Key"] for item in listing.get("Contents", []))


def test_a_ua_publish_writes_nothing_at_the_bucket_root(s3_client, local_artifacts, local_photos):
    result = publish.publish(
        local_artifacts,
        sidecars={},
        photos=local_photos,
        s3_client=s3_client,
        bucket=BUCKET,
        environment="ua",
    )

    assert result["environment"] == "ua"
    keys = _keys_in(s3_client)
    assert keys, "the publish uploaded nothing at all, so this proves nothing"
    assert all(key.startswith("environments/ua/") for key in keys), keys


def test_a_ua_publish_leaves_productions_live_keys_alone(s3_client, local_artifacts, tmp_path):
    """The failure this whole feature removes. Before it, both runs wrote
    `trails.geojson` at the root, so the second one replaced the bytes a hiker
    was in the middle of downloading."""
    publish.publish(local_artifacts, sidecars={}, photos={}, s3_client=s3_client, bucket=BUCKET, environment="production")
    published = s3_client.get_object(Bucket=BUCKET, Key="trails.geojson")["Body"].read()

    changed = tmp_path / "trails_ua.geojson"
    changed.write_text('{"type": "FeatureCollection", "features": [{"id": "only in ua"}]}')
    publish.publish(
        {"trails.geojson": {"path": str(changed), "sha256": publish.sha256_file(changed)}},
        sidecars={},
        photos={},
        s3_client=s3_client,
        bucket=BUCKET,
        environment="ua",
    )

    assert s3_client.get_object(Bucket=BUCKET, Key="trails.geojson")["Body"].read() == published
    assert s3_client.get_object(Bucket=BUCKET, Key="environments/ua/trails.geojson")["Body"].read() != published


def test_each_environment_has_its_own_manifest(s3_client, local_artifacts):
    """`latest.json` is the mutable pointer, so it is the one key two
    environments sharing would corrupt the fastest - a UA publish would move
    production's version to describe bytes production does not have."""
    publish.publish(local_artifacts, sidecars={}, photos={}, s3_client=s3_client, bucket=BUCKET, environment="production")
    publish.publish(local_artifacts, sidecars={}, photos={}, s3_client=s3_client, bucket=BUCKET, environment="ua")

    production = json.loads(s3_client.get_object(Bucket=BUCKET, Key="latest.json")["Body"].read())
    ua = json.loads(s3_client.get_object(Bucket=BUCKET, Key="environments/ua/latest.json")["Body"].read())
    assert production["version"] != ua["version"]


def test_a_manifest_names_unscoped_artifacts_in_every_environment(s3_client, local_artifacts):
    """What makes a manifest portable between environments, and what lets the
    client stay unaware that environments exist: an artifact is
    `trails.geojson` everywhere, and which bytes that names is decided by the
    base URL the build was given."""
    publish.publish(local_artifacts, sidecars={}, photos={}, s3_client=s3_client, bucket=BUCKET, environment="ua")

    manifest = json.loads(s3_client.get_object(Bucket=BUCKET, Key="environments/ua/latest.json")["Body"].read())
    assert set(manifest["artifacts"]) == set(local_artifacts)


def test_an_environments_publish_diffs_against_its_own_manifest(s3_client, local_artifacts):
    """Otherwise UA's first publish would read production's manifest, find
    every hash already matching, upload nothing, and leave UA with a pointer
    to artifacts that are not in UA's tree."""
    publish.publish(local_artifacts, sidecars={}, photos={}, s3_client=s3_client, bucket=BUCKET, environment="production")

    result = publish.publish(local_artifacts, sidecars={}, photos={}, s3_client=s3_client, bucket=BUCKET, environment="ua")

    assert sorted(result["uploaded"]) == sorted(local_artifacts)
    assert result["skipped"] == []


def test_photos_are_uploaded_per_environment(s3_client, local_artifacts, local_photos):
    """`photos/` is the one hiker-facing prefix objects are deleted from, so a
    shared prefix would let a withdrawal rehearsed in UA take the photograph
    out of production. The cost is one copy of the corpus per environment,
    which is the cheap side of that trade."""
    publish.publish(local_artifacts, sidecars={}, photos=local_photos, s3_client=s3_client, bucket=BUCKET, environment="ua")

    # The published prefix, not PHOTOS_DIRNAME - that names the local directory
    # the bytes are read from (`poi_photos/`), which is deliberately not what
    # they are served under.
    keys = _keys_in(s3_client)
    assert any(key.startswith("environments/ua/photos/") for key in keys), keys
    assert not any(key.startswith("photos/") for key in keys), keys


def test_a_publish_with_no_environment_set_refuses(monkeypatch, s3_client, local_artifacts):
    """The autouse fixture sets one for every other test in this file; this is
    the one that takes it away. Unset must be an error rather than production,
    because the only thing a default could safely be is the one that overwrites
    what hikers have already downloaded."""
    monkeypatch.delenv(data_env.ENVIRONMENT_VAR, raising=False)

    with pytest.raises(data_env.UnknownEnvironment):
        publish.publish(local_artifacts, sidecars={}, photos={}, s3_client=s3_client, bucket=BUCKET)

    assert _keys_in(s3_client) == []


def test_an_unknown_environment_refuses_before_anything_uploads(s3_client, local_artifacts):
    with pytest.raises(data_env.UnknownEnvironment):
        publish.publish(local_artifacts, sidecars={}, photos={}, s3_client=s3_client, bucket=BUCKET, environment="staging")

    assert _keys_in(s3_client) == []


def test_the_log_says_which_environment_it_published_to(monkeypatch, capsys, s3_client, local_artifacts):
    """Which environment a job wrote to is the fact this mechanism exists to
    keep straight, so a log that leaves the reader inferring it from the
    workflow's name is the log of the run that will be misread."""
    monkeypatch.setenv(data_env.ENVIRONMENT_VAR, "ua")
    monkeypatch.setattr(publish, "collect_artifacts", lambda: local_artifacts)
    monkeypatch.setattr(publish, "collect_sidecars", dict)
    monkeypatch.setattr(publish, "collect_photos", dict)
    monkeypatch.setattr(publish.boto3, "client", lambda *a, **k: s3_client)
    monkeypatch.setenv("R2_BUCKET", BUCKET)
    monkeypatch.setenv("R2_ENDPOINT_URL", "https://unused.invalid")
    monkeypatch.setenv("R2_ACCESS_KEY_ID", "unused")
    monkeypatch.setenv("R2_SECRET_ACCESS_KEY", "unused")

    publish.main()

    out = capsys.readouterr().out
    assert "ua environment" in out
    assert "environments/ua/" in out


# ---------------------------------------------------------------------------
# How artifacts are STORED, as against which of them are (#717).
#
# Every object used to land with no Content-Encoding, no Cache-Control and, for
# .geojson, no Content-Type - so the bucket served 21.5 MB of text to deliver
# 5.3 MB of information, on every hiker's first launch. These check the headers
# rather than the compression ratio: what a given input gzips to is zlib's
# business, and what a client can read is ours.
# ---------------------------------------------------------------------------


def test_text_artifacts_are_stored_gzipped_and_typed(s3_client, local_artifacts):
    publish.publish(local_artifacts, s3_client=s3_client, bucket=BUCKET)

    stored = s3_client.get_object(Bucket=BUCKET, Key="trails.geojson")
    assert stored["ContentEncoding"] == "gzip"
    assert stored["ContentType"] == "application/geo+json"
    # The bytes in the bucket really are gzip, and really are the artifact.
    # `fetch` decodes this transparently, which is why the published sha256
    # below can stay the hash of the file on disk.
    assert json.loads(gzip.decompress(stored["Body"].read())) == {
        "type": "FeatureCollection",
        "features": [],
    }


def test_the_published_hash_is_still_of_the_uncompressed_bytes(s3_client, local_artifacts):
    # The whole safety of serving these compressed rests on this. A client's
    # fetch decodes before its code sees a byte, so client/src/lib/trailData.ts
    # hashes the file as it was on disk - if the manifest recorded the gzipped
    # hash instead, every download would be rejected as corrupt.
    publish.publish(local_artifacts, s3_client=s3_client, bucket=BUCKET)

    manifest = json.loads(s3_client.get_object(Bucket=BUCKET, Key="latest.json")["Body"].read())
    assert manifest["artifacts"]["trails.geojson"]["sha256"] == local_artifacts["trails.geojson"]["sha256"]


def test_range_readable_archives_are_never_encoded(tmp_path, s3_client):
    # .pmtiles is read by byte range - the client seeks within the archive
    # (map/pmtilesSource.ts) and resumes partial transfers with a Range header
    # (lib/archiveDownload.ts). A stored Content-Encoding makes a range refer
    # to compressed offsets, which breaks both, so this must never be "helped"
    # into the compressible table.
    archive = tmp_path / "background.pmtiles"
    archive.write_bytes(b"PMTiles" + b"\0" * 512)
    artifacts = {"background.pmtiles": {"path": str(archive), "sha256": publish.sha256_file(archive)}}

    publish.publish(artifacts, s3_client=s3_client, bucket=BUCKET)

    stored = s3_client.get_object(Bucket=BUCKET, Key="background.pmtiles")
    assert "ContentEncoding" not in stored
    assert stored["ContentType"] == "application/vnd.pmtiles"
    assert stored["Body"].read() == archive.read_bytes()


def test_the_manifest_is_never_cached(s3_client, local_artifacts):
    # latest.json says which version is current. A stale copy would have a
    # client check freshly downloaded bytes against a superseded hash and
    # discard a good download.
    publish.publish(local_artifacts, s3_client=s3_client, bucket=BUCKET)

    stored = s3_client.get_object(Bucket=BUCKET, Key="latest.json")
    assert stored["CacheControl"] == "no-cache"
    assert "ContentEncoding" not in stored


def test_collect_gathers_the_drought_bands(tmp_path, monkeypatch):
    """#720's artifact, and the one this file did not cover when it shipped.

    `collect_artifacts` walked a hardcoded pair of manifest names, so an
    export script that wrote a third was built every hour and uploaded never.
    Nothing failed: the publish log read "uploaded
    ['conditions/atc_updates.json']" and every step was green.
    """
    monkeypatch.setattr(publish, "PROCESSED_DIR", tmp_path)
    conditions_dir = tmp_path / "conditions"
    conditions_dir.mkdir()
    drought = conditions_dir / "drought.json"
    drought.write_text('{"generated_at": "2026-08-15T23:00:00Z", "drought": []}')
    (tmp_path / "drought_manifest.json").write_text(
        json.dumps({"artifacts": {"drought": {"path": str(drought), "sha256": "d40u9h7", "count": 4}}})
    )

    artifacts = publish.collect_artifacts()

    assert artifacts["conditions/drought.json"]["sha256"] == "d40u9h7"


def test_every_conditions_manifest_an_export_writes_is_one_publish_collects():
    """The guard for the class of bug above, rather than for that one instance.

    An export script that writes a manifest into `data/processed/` and is not
    named in `CONDITIONS_MANIFESTS` publishes nothing, silently. This reads
    the export scripts for the manifest filenames they actually write and
    holds them against the tuple.

    It deliberately covers only the manifests that land in `conditions/` -
    the trails, POI, elevation, spurs and club-section manifests are each
    collected by their own named block in `collect_artifacts`, so a missing
    entry there is a different (and louder) failure.
    """
    pipeline_dir = pathlib.Path(publish.__file__).resolve().parent
    written = set()
    for script in sorted(pipeline_dir.glob("export_*.py")):
        source = script.read_text()
        # The artifact family is identifiable from the export itself: these
        # are the scripts that write into data/processed/conditions/.
        if "PAYLOAD = " not in source or '"conditions"' not in source:
            continue
        for match in re.finditer(r'"([a-z_]+_manifest\.json)"', source):
            written.add(match.group(1))

    assert written, "found no conditions exports - this guard has stopped guarding"
    assert written <= set(publish.CONDITIONS_MANIFESTS), (
        f"these manifests are written but never published: {sorted(written - set(publish.CONDITIONS_MANIFESTS))}"
    )


def test_collect_gathers_the_stretch_units_from_their_manifests(tmp_path, monkeypatch):
    """#556: each sheet's cut leaves <family>_stretches_manifest.json in
    PROCESSED_DIR and every artifact it names - stretches, context, the
    coverage index - publishes like any other."""
    monkeypatch.setattr(publish, "PROCESSED_DIR", tmp_path)
    stretch = tmp_path / "at_basemap_stretch_00.pmtiles"
    stretch.write_bytes(b"stretch-bytes")
    index = tmp_path / "at_basemap_stretches.json"
    index.write_text("{}")
    (tmp_path / "at_basemap_stretches_manifest.json").write_text(
        json.dumps(
            {
                "artifacts": {
                    "at_basemap_stretch_00.pmtiles": {"path": str(stretch), "sha256": "a" * 64, "size_bytes": 13},
                    "at_basemap_stretches.json": {"path": str(index), "sha256": "b" * 64, "size_bytes": 2},
                },
                "stats": {"seam_duplication_pct": 1.0},
            }
        )
    )

    artifacts = publish.collect_artifacts()

    assert artifacts["at_basemap_stretch_00.pmtiles"]["sha256"] == "a" * 64
    assert artifacts["at_basemap_stretches.json"]["sha256"] == "b" * 64


def test_collect_publishes_every_artifacts_measured_size(tmp_path, monkeypatch):
    """#505's third ask, needed for real at stretch scale (#556): size_bytes
    is measured from the built file, never hand-kept."""
    monkeypatch.setattr(publish, "PROCESSED_DIR", tmp_path)
    path = tmp_path / "background.pmtiles"
    path.write_bytes(b"0123456789")

    artifacts = publish.collect_artifacts()

    assert artifacts["background.pmtiles"]["size_bytes"] == 10


def test_the_manifest_version_carries_size_bytes(tmp_path, s3_client):
    """The size rides beside the hash in latest.json, so drift between the
    advertised figure and the served bytes is visible in a manifest diff -
    and per-stretch download prompts have an honest number to print."""
    artifact = tmp_path / "background.pmtiles"
    artifact.write_bytes(b"0123456789")

    result = publish.publish(
        artifacts={"background.pmtiles": {"path": str(artifact), "sha256": publish.sha256_file(artifact), "size_bytes": 10}},
        sidecars={},
        photos={},
        s3_client=s3_client,
        bucket=BUCKET,
    )

    assert result["version_written"] is True
    body = s3_client.get_object(Bucket=BUCKET, Key="latest.json")["Body"].read()
    manifest = json.loads(body)
    assert manifest["artifacts"]["background.pmtiles"]["size_bytes"] == 10
