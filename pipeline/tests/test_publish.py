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
from lib.photo_store import PHOTOS_DIRNAME, photo_digest, photo_key

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


def test_collect_sidecars_finds_build_state_where_the_capture_writes_it(tmp_path, monkeypatch):
    monkeypatch.setattr(publish, "PROCESSED_DIR", tmp_path)
    (tmp_path / "build_state.json").write_text("{}")

    assert set(publish.collect_sidecars()) == {"build_state.json"}


def test_collect_sidecars_is_empty_when_no_capture_ran(tmp_path, monkeypatch):
    monkeypatch.setattr(publish, "PROCESSED_DIR", tmp_path)

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


def test_photos_alone_do_not_write_a_new_version(s3_client, local_artifacts, local_photos):
    """A photo only becomes visible through a poi artifact that references
    it; that artifact's bytes changing is the real event. Bumping the version
    for a photo would be the no-op bump publish() exists to prevent."""
    publish.publish(local_artifacts, sidecars={}, photos={}, s3_client=s3_client, bucket=BUCKET)

    result = publish.publish(local_artifacts, sidecars={}, photos=local_photos, s3_client=s3_client, bucket=BUCKET)

    assert result["photos_uploaded"]  # they did upload
    assert result["version_written"] is False  # and wrote no version
    assert publish.MANIFEST_KEY not in result["uploaded"]


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
