"""Tests for lib/planetiler_sources.py and fetch_planetiler_sources.py (#1970).

Every download here is a fake that writes a small zip archive, and the raw
bucket is either FakeCopy or moto, so nothing reaches a network. What these
pin is the decision per source: keep the cache's copy, take the bucket's,
fetch, or keep an older copy; that the bucket ends up holding what the run
has; that a bucket which fails costs a warning and never the run; and that
the run fails only when a source has no copy anywhere.
"""

from __future__ import annotations

import io
import json
import zipfile
from datetime import date, timedelta
from pathlib import Path

import boto3
import pytest
import requests
import yaml
from moto import mock_aws

import fetch_planetiler_sources
import publish
from lib.planetiler_sources import (
    BUCKET_PREFIX,
    MANIFEST_NAME,
    MAX_AGE_DAYS,
    SOURCES,
    SOURCES_DIR,
    CopyFailed,
    Outcome,
    SourceUnavailable,
    ensure_sources,
    github_output_marker,
    planetiler_args,
)

TODAY = date(2026, 11, 4)
WORKFLOW = Path(__file__).resolve().parents[2] / ".github" / "workflows" / "build-basemap.yml"
BUCKET = "raw-bucket-under-test"


@pytest.fixture(autouse=True)
def no_bucket_settings(monkeypatch):
    """No test here reads this machine's own R2 settings by accident."""
    for name in fetch_planetiler_sources.RAW_BUCKET_SETTINGS:
        monkeypatch.delenv(name, raising=False)


def _zip(payload: bytes) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("payload.txt", payload)
    return buffer.getvalue()


class FakeDownload:
    """Stands in for download_with_retry: records each source it was asked
    for, fails the ones named in `failing`, and otherwise writes `body` (a
    zip archive naming the source, by default) to `dest`."""

    def __init__(self, failing: tuple[str, ...] = (), body: bytes | None = None):
        self.asked: list[str] = []
        self.failing = set(failing)
        self.body = body

    def __call__(self, url: str, dest: Path, *, label: str | None = None, **_kwargs) -> Path:
        self.asked.append(label)
        if label in self.failing:
            raise requests.exceptions.ConnectionError("Connection reset by peer")
        dest.write_bytes(self.body if self.body is not None else _zip(label.encode()))
        return dest


def _seed(sources_dir: Path, *, fetched: date, content: bytes | None = None) -> dict[str, bytes]:
    """Every source on disk with a manifest entry dated `fetched`."""
    sources_dir.mkdir(parents=True, exist_ok=True)
    manifest = {}
    written = {}
    for source in SOURCES:
        body = content if content is not None else _zip(b"old " + source.name.encode())
        (sources_dir / source.filename).write_bytes(body)
        manifest[source.name] = {"url": source.url, "bytes": len(body), "fetched": fetched.isoformat()}
        written[source.name] = body
    (sources_dir / MANIFEST_NAME).write_text(json.dumps(manifest))
    return written


def _manifest(sources_dir: Path) -> dict:
    return json.loads((sources_dir / MANIFEST_NAME).read_text())


class FakeCopy:
    """Stands in for the raw bucket's copy: files and a manifest in memory.
    Each method named in `failing` raises CopyFailed, as RawBucketCopy does
    for a store that refuses or does not answer."""

    def __init__(self, files: dict[str, bytes] | None = None, manifest: dict | None = None, failing: tuple[str, ...] = ()):
        self.files = dict(files or {})
        self.manifest = manifest
        self.failing = set(failing)
        self.calls: list[tuple[str, ...]] = []

    def _call(self, *call: str) -> None:
        self.calls.append(call)
        if call[0] in self.failing:
            raise CopyFailed(f"EndpointConnectionError: {call[0]} did not answer")

    def read_manifest(self) -> dict | None:
        self._call("read_manifest")
        return None if self.manifest is None else json.loads(json.dumps(self.manifest))

    def get(self, filename: str, dest: Path) -> None:
        self._call("get", filename)
        if filename not in self.files:
            raise CopyFailed("ClientError: 404 Not Found")
        dest.write_bytes(self.files[filename])

    def put(self, path: Path, filename: str) -> None:
        self._call("put", filename)
        self.files[filename] = path.read_bytes()

    def write_manifest(self, manifest: dict) -> None:
        self._call("write_manifest")
        self.manifest = json.loads(json.dumps(manifest))

    def uploaded(self) -> list[str]:
        return sorted(call[1] for call in self.calls if call[0] == "put")


def _bucket(*, fetched: date, failing: tuple[str, ...] = ()) -> FakeCopy:
    """A bucket holding every source, each with its manifest entry dated `fetched`."""
    files, manifest = {}, {}
    for source in SOURCES:
        body = _zip(b"bucket " + source.name.encode())
        files[source.filename] = body
        manifest[source.name] = {"url": source.url, "bytes": len(body), "fetched": fetched.isoformat()}
    return FakeCopy(files, manifest, failing)


def test_the_three_sources_are_planetiler_0_10_2s_own_defaults():
    """Read from build-basemap.yml run 58's argument dump (2026-11-03), the
    pinned v0.10.2 jar: `<name>_url` and `<name>_path` under data/sources.
    If the jar is bumped and its defaults move, this is the list to check,
    and planetiler_args() means the build follows this list either way."""
    assert {(s.name, s.url, s.filename) for s in SOURCES} == {
        (
            "water_polygons",
            "https://osmdata.openstreetmap.de/download/water-polygons-split-3857.zip",
            "water-polygons-split-3857.zip",
        ),
        (
            "natural_earth",
            "https://naciscdn.org/naturalearth/packages/natural_earth_vector.sqlite.zip",
            "natural_earth_vector.sqlite.zip",
        ),
        (
            "lake_centerlines",
            "https://github.com/acalcutt/osm-lakelines/releases/download/v12/lake_centerline.shp.zip",
            "lake_centerline.shp.zip",
        ),
    }


def test_the_sources_live_where_build_basemap_yml_caches_them():
    """build-basemap.yml restores and saves pipeline/data/sources
    (.github/tests/test_basemap_planetiler_sources.py holds that half)."""
    pipeline_dir = Path(fetch_planetiler_sources.__file__).resolve().parent
    assert SOURCES_DIR == pipeline_dir / "data" / "sources"
    # The save step keys on hashFiles() of this file by name.
    assert MANIFEST_NAME == "planetiler_sources.json"


def test_planetiler_is_pointed_at_exactly_the_files_fetched_here(tmp_path):
    args = planetiler_args(tmp_path)
    assert f"--water_polygons_path={tmp_path / 'water-polygons-split-3857.zip'}" in args
    assert "--water_polygons_url=https://osmdata.openstreetmap.de/download/water-polygons-split-3857.zip" in args
    assert len(args) == 2 * len(SOURCES)


def test_an_empty_directory_fetches_all_three_and_records_each(tmp_path):
    download = FakeDownload()
    landed: list[str] = []

    outcomes = ensure_sources(tmp_path, today=TODAY, download=download, on_fetched=landed.append)

    assert [o.action for o in outcomes] == ["fetched"] * 3
    assert sorted(download.asked) == sorted(s.name for s in SOURCES)
    assert sorted(landed) == sorted(s.name for s in SOURCES)
    manifest = _manifest(tmp_path)
    for source in SOURCES:
        path = tmp_path / source.filename
        assert zipfile.is_zipfile(path)
        assert manifest[source.name] == {"url": source.url, "bytes": path.stat().st_size, "fetched": "2026-11-04"}
    assert not list(tmp_path.glob("*.incoming")), "no half-fetched file is left beside the sources"


def test_a_set_fetched_29_days_ago_is_kept_without_asking_anyone(tmp_path):
    _seed(tmp_path, fetched=TODAY - timedelta(days=MAX_AGE_DAYS - 1))
    download = FakeDownload()

    outcomes = ensure_sources(tmp_path, today=TODAY, download=download)

    assert download.asked == []
    assert [o.action for o in outcomes] == ["kept"] * 3


def test_a_set_fetched_30_days_ago_is_fetched_again(tmp_path):
    _seed(tmp_path, fetched=TODAY - timedelta(days=MAX_AGE_DAYS))
    download = FakeDownload()

    outcomes = ensure_sources(tmp_path, today=TODAY, download=download)

    assert [o.action for o in outcomes] == ["fetched"] * 3
    assert {entry["fetched"] for entry in _manifest(tmp_path).values()} == {"2026-11-04"}


def test_a_failed_refetch_keeps_the_older_copy_untouched(tmp_path):
    """The run 57 and 58 case, once a copy exists: osmdata.openstreetmap.de
    refuses, and the month-old water polygons draw the basemap anyway."""
    old = _seed(tmp_path, fetched=TODAY - timedelta(days=45))
    download = FakeDownload(failing=("water_polygons",))

    outcomes = {o.name: o for o in ensure_sources(tmp_path, today=TODAY, download=download)}

    assert outcomes["water_polygons"].action == "kept_stale"
    assert "2026-09-20" in outcomes["water_polygons"].detail
    assert (tmp_path / "water-polygons-split-3857.zip").read_bytes() == old["water_polygons"]
    assert _manifest(tmp_path)["water_polygons"]["fetched"] == "2026-09-20"
    assert outcomes["natural_earth"].action == "fetched"


def test_a_source_with_no_copy_that_cannot_be_fetched_stops_the_run_after_the_others_land(tmp_path):
    """The first run after this change, with osmdata.openstreetmap.de as it
    was on 2026-11-03: neither the cache nor the bucket has a copy yet, so
    the run fails, in this step, about two minutes into the job. The other
    two still land and are reported, so the save step keeps them and the
    next run asks only for the water."""
    download = FakeDownload(failing=("water_polygons",))
    landed: list[str] = []

    with pytest.raises(SourceUnavailable, match="water_polygons: https://osmdata.openstreetmap.de"):
        ensure_sources(tmp_path, today=TODAY, download=download, on_fetched=landed.append)

    assert sorted(landed) == ["lake_centerlines", "natural_earth"]
    assert not (tmp_path / "water-polygons-split-3857.zip").exists()
    assert set(_manifest(tmp_path)) == {"lake_centerlines", "natural_earth"}


def test_an_answer_that_is_not_a_zip_never_replaces_a_copy(tmp_path):
    """A host that answers 200 with an error page must not overwrite the
    water polygons a month of builds has been drawing."""
    old = _seed(tmp_path, fetched=TODAY - timedelta(days=45))
    download = FakeDownload(body=b"<html>Service Unavailable</html>")

    outcomes = ensure_sources(tmp_path, today=TODAY, download=download)

    assert [o.action for o in outcomes] == ["kept_stale"] * 3
    for source in SOURCES:
        assert (tmp_path / source.filename).read_bytes() == old[source.name]
    assert not list(tmp_path.glob("*.incoming"))


@pytest.mark.parametrize(
    "spoil",
    [
        pytest.param(lambda d: (d / MANIFEST_NAME).unlink(), id="no manifest"),
        pytest.param(lambda d: (d / "water-polygons-split-3857.zip").write_bytes(b"trunc"), id="size disagrees"),
        pytest.param(
            lambda d: (d / MANIFEST_NAME).write_text(
                json.dumps(
                    {**_manifest(d), "water_polygons": {**_manifest(d)["water_polygons"], "url": "https://old.example/w.zip"}}
                )
            ),
            id="another url",
        ),
    ],
)
def test_a_young_file_the_manifest_cannot_vouch_for_is_fetched_again(tmp_path, spoil):
    _seed(tmp_path, fetched=TODAY - timedelta(days=1))
    spoil(tmp_path)
    download = FakeDownload()

    outcomes = {o.name: o.action for o in ensure_sources(tmp_path, today=TODAY, download=download)}

    assert outcomes["water_polygons"] == "fetched"
    assert zipfile.is_zipfile(tmp_path / "water-polygons-split-3857.zip")


def test_a_file_nobody_vouches_for_is_not_kept_when_its_refetch_fails(tmp_path):
    """Kept-on-failure is only for a copy the manifest describes. A file of
    unknown provenance whose refetch fails stops the run instead."""
    _seed(tmp_path, fetched=TODAY - timedelta(days=1))
    (tmp_path / MANIFEST_NAME).unlink()

    with pytest.raises(SourceUnavailable, match="water_polygons"):
        ensure_sources(tmp_path, today=TODAY, download=FakeDownload(failing=("water_polygons",)))


def test_what_a_killed_fetch_left_behind_is_cleared_before_anything_else(tmp_path):
    """A job killed mid-download skips download_with_retry's own cleanup,
    and the save step runs on always(), so a cache entry can carry the
    half-written files back into the next run."""
    _seed(tmp_path, fetched=TODAY - timedelta(days=1))
    leftovers = [
        tmp_path / "water-polygons-split-3857.zip.incoming",
        tmp_path / "water-polygons-split-3857.zip.incoming.part",
        tmp_path / "water-polygons-split-3857.zip.incoming.9fA0b3C1",  # boto3's own, for a bucket download
        tmp_path / f"{MANIFEST_NAME}.tmp",
    ]
    for leftover in leftovers:
        leftover.write_bytes(b"half")

    ensure_sources(tmp_path, today=TODAY, download=FakeDownload())

    assert [p.name for p in leftovers if p.exists()] == []


def test_a_bug_in_a_fetch_fails_the_run_rather_than_keeping_a_stale_copy(tmp_path):
    """Kept-on-failure covers the network, the disk and a non-zip answer.
    A TypeError is a defect in this code, and a green run with a warning
    would hide it for a month."""
    _seed(tmp_path, fetched=TODAY - timedelta(days=45))

    def broken(url, dest, **_kwargs):
        raise TypeError("download() got an unexpected keyword argument")

    with pytest.raises(TypeError):
        ensure_sources(tmp_path, today=TODAY, download=broken)


def test_the_save_marker_is_written_once_however_many_sources_land(tmp_path):
    output = tmp_path / "github_output"
    mark = github_output_marker(str(output))
    for name in ("water_polygons", "natural_earth", "lake_centerlines"):
        mark(name)
    assert output.read_text() == "fetched=true\n"


def test_outside_actions_the_save_marker_writes_nothing(tmp_path, monkeypatch):
    monkeypatch.delenv("GITHUB_OUTPUT", raising=False)
    github_output_marker()("water_polygons")
    assert list(tmp_path.iterdir()) == []


def test_the_command_exits_1_naming_the_source_it_could_not_get(monkeypatch, capsys):
    def unavailable(*_args, **_kwargs):
        raise SourceUnavailable("water_polygons: https://osmdata.openstreetmap.de/... could not be fetched")

    monkeypatch.setattr(fetch_planetiler_sources, "ensure_sources", unavailable)

    assert fetch_planetiler_sources.main([]) == 1
    assert "::error::Planetiler's profile sources are incomplete: water_polygons" in capsys.readouterr().out


def test_the_command_warns_on_a_kept_older_copy_and_still_succeeds(monkeypatch, capsys):
    monkeypatch.setattr(
        fetch_planetiler_sources,
        "ensure_sources",
        lambda *_a, **_k: [
            Outcome("water_polygons", "kept_stale", "refetch failed; keeping the copy fetched 2026-09-20, 45 days ago"),
            Outcome("natural_earth", "kept", "fetched 2026-11-01, 3 days ago"),
        ],
    )

    assert fetch_planetiler_sources.main([]) == 0
    out = capsys.readouterr().out
    assert "::warning::water_polygons: kept_stale" in out
    assert "natural_earth: kept - fetched 2026-11-01" in out


# --- The raw bucket's copy ------------------------------------------------------------------------


def _actions(outcomes: list[Outcome]) -> dict[str, list[str]]:
    """Each source's outcomes, in order, by name."""
    actions: dict[str, list[str]] = {}
    for outcome in outcomes:
        actions.setdefault(outcome.name, []).append(outcome.action)
    return actions


def test_a_cold_cache_takes_a_young_bucket_copy_and_asks_no_host(tmp_path):
    """The eviction PR #1978's review raised (finding 1): a run after 8 or
    more idle days starts with an empty cache, and the bucket answers in
    place of osmdata.openstreetmap.de. Each copy keeps the date it was
    really fetched, so its 30 days count from then, and the save step is
    told to keep it."""
    bucket = _bucket(fetched=TODAY - timedelta(days=10))
    download = FakeDownload()
    landed: list[str] = []

    outcomes = ensure_sources(tmp_path, today=TODAY, download=download, on_fetched=landed.append, copy=bucket)

    assert [o.action for o in outcomes] == ["from_bucket"] * 3
    assert download.asked == []
    assert sorted(landed) == sorted(s.name for s in SOURCES)
    assert _manifest(tmp_path) == bucket.manifest
    for source in SOURCES:
        assert (tmp_path / source.filename).read_bytes() == bucket.files[source.filename]
    assert bucket.uploaded() == []
    assert ("write_manifest",) not in bucket.calls


def test_a_bucket_copy_as_old_as_max_age_is_fetched_again_and_replaced_in_the_bucket(tmp_path):
    bucket = _bucket(fetched=TODAY - timedelta(days=MAX_AGE_DAYS))

    outcomes = _actions(ensure_sources(tmp_path, today=TODAY, download=FakeDownload(), copy=bucket))

    assert outcomes == {source.name: ["fetched", "uploaded"] for source in SOURCES}
    assert bucket.uploaded() == sorted(s.filename for s in SOURCES)
    assert bucket.calls[-1] == ("write_manifest",), "the manifest goes last, after every file it vouches for"
    assert bucket.manifest == _manifest(tmp_path)
    assert {entry["fetched"] for entry in bucket.manifest.values()} == {"2026-11-04"}


def test_with_its_host_down_a_cold_cache_keeps_the_buckets_older_copy(tmp_path):
    """Runs 57 and 58 again, after an eviction: no cache, a bucket copy past
    MAX_AGE_DAYS, and osmdata.openstreetmap.de not answering. The bucket's
    older copy draws the basemap, where before it the run failed."""
    bucket = _bucket(fetched=TODAY - timedelta(days=45))
    download = FakeDownload(failing=("water_polygons",))

    outcomes = ensure_sources(tmp_path, today=TODAY, download=download, copy=bucket)

    water = next(o for o in outcomes if o.name == "water_polygons")
    assert water.action == "kept_stale"
    assert "using the raw bucket's copy fetched 2026-09-20, 45 days ago" in water.detail
    assert (tmp_path / "water-polygons-split-3857.zip").read_bytes() == bucket.files["water-polygons-split-3857.zip"]
    assert _manifest(tmp_path)["water_polygons"]["fetched"] == "2026-09-20"
    assert _actions(outcomes)["natural_earth"] == ["fetched", "uploaded"]
    assert bucket.uploaded() == ["lake_centerline.shp.zip", "natural_earth_vector.sqlite.zip"]


@pytest.mark.parametrize(
    ("cache_days", "bucket_days", "stands"),
    [pytest.param(50, 40, "bucket", id="the bucket's is newer"), pytest.param(40, 50, "cache", id="the cache's is newer")],
)
def test_with_its_host_down_the_newer_of_two_older_copies_stands(tmp_path, cache_days, bucket_days, stands):
    cache = _seed(tmp_path, fetched=TODAY - timedelta(days=cache_days))
    bucket = _bucket(fetched=TODAY - timedelta(days=bucket_days))
    download = FakeDownload(failing=tuple(s.name for s in SOURCES))

    outcomes = _actions(ensure_sources(tmp_path, today=TODAY, download=download, copy=bucket))

    for source in SOURCES:
        expected = bucket.files[source.filename] if stands == "bucket" else cache[source.name]
        assert (tmp_path / source.filename).read_bytes() == expected
    if stands == "bucket":
        assert outcomes == {source.name: ["kept_stale"] for source in SOURCES}
    else:
        # The bucket is given the newer copy, so it is the better fallback next time.
        assert outcomes == {source.name: ["kept_stale", "uploaded"] for source in SOURCES}


def test_a_bucket_copy_whose_size_disagrees_with_its_entry_is_never_used(tmp_path):
    bucket = _bucket(fetched=TODAY - timedelta(days=3))
    bucket.files["water-polygons-split-3857.zip"] = bucket.files["water-polygons-split-3857.zip"][:-7]

    outcomes = ensure_sources(tmp_path, today=TODAY, download=FakeDownload(), copy=bucket)

    water = [o for o in outcomes if o.name == "water_polygons"]
    assert [o.action for o in water] == ["bucket_unusable", "fetched", "uploaded"]
    assert "its manifest entry says" in water[0].detail
    assert zipfile.is_zipfile(tmp_path / "water-polygons-split-3857.zip")
    assert not list(tmp_path.glob("*.incoming*"))
    assert bucket.manifest["water_polygons"]["fetched"] == "2026-11-04", "the host's copy repairs the bucket's"


def test_a_bucket_copy_that_is_not_a_zip_is_never_used(tmp_path):
    bucket = _bucket(fetched=TODAY - timedelta(days=3))
    page = b"<html>Service Unavailable</html>"
    bucket.files["water-polygons-split-3857.zip"] = page
    bucket.manifest["water_polygons"]["bytes"] = len(page)

    outcomes = _actions(ensure_sources(tmp_path, today=TODAY, download=FakeDownload(), copy=bucket))

    assert outcomes["water_polygons"] == ["bucket_unusable", "fetched", "uploaded"]
    assert zipfile.is_zipfile(tmp_path / "water-polygons-split-3857.zip")


def test_a_bucket_entry_for_another_url_is_not_trusted(tmp_path):
    bucket = _bucket(fetched=TODAY - timedelta(days=3))
    bucket.manifest["natural_earth"]["url"] = "https://old.example/natural_earth.zip"
    download = FakeDownload()

    outcomes = _actions(ensure_sources(tmp_path, today=TODAY, download=download, copy=bucket))

    assert download.asked == ["natural_earth"]
    assert outcomes["natural_earth"] == ["fetched", "uploaded"]
    assert bucket.manifest["natural_earth"]["url"] == "https://naciscdn.org/naturalearth/packages/natural_earth_vector.sqlite.zip"


@pytest.mark.parametrize(
    "spoil",
    [
        pytest.param(lambda bucket: bucket.failing.add("read_manifest"), id="it does not answer"),
        pytest.param(lambda bucket: setattr(bucket, "manifest", ["not", "an", "object"]), id="it is not a JSON object"),
    ],
)
def test_a_bucket_whose_manifest_cannot_be_read_is_neither_read_nor_written(tmp_path, spoil):
    """A failed read cannot tell an empty bucket from one that did not
    answer, so nothing is written, and the entries nobody saw survive."""
    bucket = _bucket(fetched=TODAY - timedelta(days=3))
    spoil(bucket)
    download = FakeDownload()

    outcomes = ensure_sources(tmp_path, today=TODAY, download=download, copy=bucket)

    assert (outcomes[0].name, outcomes[0].action) == ("raw_bucket", "bucket_unusable")
    assert "nothing is read from it or written to it this run" in outcomes[0].detail
    assert sorted(download.asked) == sorted(s.name for s in SOURCES)
    assert bucket.calls == [("read_manifest",)]


def test_a_bucket_that_fails_mid_read_sends_the_source_to_its_host(tmp_path):
    bucket = _bucket(fetched=TODAY - timedelta(days=3), failing=("get",))
    download = FakeDownload()

    outcomes = _actions(ensure_sources(tmp_path, today=TODAY, download=download, copy=bucket))

    assert sorted(download.asked) == sorted(s.name for s in SOURCES)
    assert outcomes["water_polygons"] == ["bucket_unusable", "fetched", "uploaded"]


def test_a_bucket_copy_that_failed_once_is_not_tried_again_when_the_host_fails_too(tmp_path):
    bucket = _bucket(fetched=TODAY - timedelta(days=3), failing=("get",))
    download = FakeDownload(failing=("water_polygons",))

    with pytest.raises(SourceUnavailable, match="water_polygons"):
        ensure_sources(tmp_path, today=TODAY, download=download, copy=bucket)

    assert bucket.calls.count(("get", "water-polygons-split-3857.zip")) == 1


def test_an_upload_that_fails_costs_a_warning_and_never_the_run(tmp_path):
    bucket = FakeCopy(failing=("put",))

    outcomes = _actions(ensure_sources(tmp_path, today=TODAY, download=FakeDownload(), copy=bucket))

    assert outcomes == {source.name: ["fetched", "upload_failed"] for source in SOURCES}
    assert ("write_manifest",) not in bucket.calls, "it has nothing new to vouch for"
    assert all(zipfile.is_zipfile(tmp_path / s.filename) for s in SOURCES)


def test_a_manifest_that_cannot_be_written_costs_a_warning_and_never_the_run(tmp_path):
    bucket = FakeCopy(failing=("write_manifest",))

    outcomes = ensure_sources(tmp_path, today=TODAY, download=FakeDownload(), copy=bucket)

    assert (outcomes[-1].name, outcomes[-1].action) == ("raw_bucket", "upload_failed")
    assert bucket.uploaded() == sorted(s.filename for s in SOURCES)
    assert bucket.manifest is None


def test_a_young_cache_copy_the_bucket_lacks_is_uploaded_without_asking_a_host(tmp_path):
    """The first run with a bucket after runs that filled the cache, or after
    an upload that failed: the bucket is brought up to date from the cache,
    so it is ready for the next eviction."""
    cache = _seed(tmp_path, fetched=TODAY - timedelta(days=3))
    bucket = FakeCopy()
    download = FakeDownload()

    outcomes = _actions(ensure_sources(tmp_path, today=TODAY, download=download, copy=bucket))

    assert download.asked == []
    assert outcomes == {source.name: ["kept", "uploaded"] for source in SOURCES}
    assert bucket.files == {s.filename: cache[s.name] for s in SOURCES}
    assert bucket.manifest == _manifest(tmp_path)


def test_a_bucket_holding_a_newer_copy_is_never_given_an_older_one(tmp_path):
    _seed(tmp_path, fetched=TODAY - timedelta(days=3))
    bucket = _bucket(fetched=TODAY - timedelta(days=1))

    outcomes = _actions(ensure_sources(tmp_path, today=TODAY, download=FakeDownload(), copy=bucket))

    assert outcomes == {source.name: ["kept"] for source in SOURCES}
    assert bucket.uploaded() == []
    assert ("write_manifest",) not in bucket.calls


def test_a_source_with_no_copy_anywhere_fails_the_run_only_after_the_bucket_has_the_others(tmp_path):
    bucket = FakeCopy()
    download = FakeDownload(failing=("water_polygons",))

    with pytest.raises(SourceUnavailable, match="water_polygons: https://osmdata.openstreetmap.de") as failure:
        ensure_sources(tmp_path, today=TODAY, download=download, copy=bucket)

    assert bucket.uploaded() == ["lake_centerline.shp.zip", "natural_earth_vector.sqlite.zip"]
    assert set(bucket.manifest) == {"lake_centerlines", "natural_earth"}
    assert _actions(failure.value.outcomes)["natural_earth"] == ["fetched", "uploaded"]


def test_a_bug_in_the_bucket_copy_fails_the_run_rather_than_reading_as_an_outage(tmp_path):
    bucket = _bucket(fetched=TODAY - timedelta(days=3))

    def broken(filename, dest):
        raise TypeError("get() takes 2 positional arguments but 3 were given")

    bucket.get = broken

    with pytest.raises(TypeError):
        ensure_sources(tmp_path, today=TODAY, download=FakeDownload(), copy=bucket)


@pytest.fixture
def raw_bucket():
    """RawBucketCopy over moto's S3, so the boto3 calls themselves run."""
    with mock_aws():
        client = boto3.client("s3", region_name="us-east-1")
        client.create_bucket(Bucket=BUCKET)
        yield fetch_planetiler_sources.RawBucketCopy(client, BUCKET)


def test_the_raw_bucket_copy_keeps_each_file_and_its_manifest_under_planetiler_sources(raw_bucket, tmp_path):
    assert raw_bucket.read_manifest() is None, "a bucket with no manifest yet is empty, not failing"
    original = tmp_path / "lake_centerline.shp.zip"
    original.write_bytes(_zip(b"lakes"))
    entry = {"lake_centerlines": {"url": "https://example.invalid/l.zip", "bytes": 1, "fetched": "2026-11-04"}}

    raw_bucket.put(original, original.name)
    raw_bucket.write_manifest(entry)
    raw_bucket.get(original.name, tmp_path / "back.zip")

    assert (tmp_path / "back.zip").read_bytes() == original.read_bytes()
    assert raw_bucket.read_manifest() == entry
    keys = sorted(item["Key"] for item in raw_bucket.client.list_objects_v2(Bucket=BUCKET)["Contents"])
    assert keys == [f"{BUCKET_PREFIX}/lake_centerline.shp.zip", f"{BUCKET_PREFIX}/{MANIFEST_NAME}"]


def test_a_bucket_that_refuses_raises_copy_failed_and_never_answers_empty(tmp_path):
    """A refusal read as "no manifest yet" would upload all 1.4 GB and
    overwrite the bucket's manifest on every run, so only a missing key is
    an empty answer."""
    with mock_aws():
        refusing = fetch_planetiler_sources.RawBucketCopy(boto3.client("s3", region_name="us-east-1"), "no-such-bucket")
        (tmp_path / "w.zip").write_bytes(_zip(b"water"))

        with pytest.raises(CopyFailed, match="NoSuchBucket"):
            refusing.read_manifest()
        with pytest.raises(CopyFailed):
            refusing.get("water-polygons-split-3857.zip", tmp_path / "back.zip")
        with pytest.raises(CopyFailed):
            refusing.put(tmp_path / "w.zip", "w.zip")
        with pytest.raises(CopyFailed):
            refusing.write_manifest({})


def test_after_an_eviction_the_next_run_reads_what_the_last_one_uploaded(raw_bucket, tmp_path):
    """Two runs nine days apart, with the real boto3 calls between them: the
    first fetches and uploads, the cache is evicted, and the second takes
    every source from the bucket and asks no host."""
    first, second = tmp_path / "first", tmp_path / "second"
    ensure_sources(first, today=TODAY - timedelta(days=9), download=FakeDownload(), copy=raw_bucket)
    download = FakeDownload()

    outcomes = ensure_sources(second, today=TODAY, download=download, copy=raw_bucket)

    assert download.asked == []
    assert [o.action for o in outcomes] == ["from_bucket"] * 3
    for source in SOURCES:
        assert (second / source.filename).read_bytes() == (first / source.filename).read_bytes()
    assert not list(second.glob("*.incoming*"))


# --- The command's settings ---------------------------------------------------------------------


def test_the_bucket_settings_are_the_ones_build_basemap_yml_gives_the_fetch_step():
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    fetch = next(step for step in workflow["jobs"]["build"]["steps"] if step.get("id") == "planetiler_sources")
    assert set(fetch["env"]) == set(fetch_planetiler_sources.RAW_BUCKET_SETTINGS)


def test_without_the_bucket_settings_the_command_warns_and_asks_the_hosts_alone(monkeypatch, capsys):
    seen: dict = {}
    monkeypatch.setattr(fetch_planetiler_sources, "ensure_sources", lambda *_a, **kwargs: seen.update(kwargs) or [])

    assert fetch_planetiler_sources.main([]) == 0
    assert seen["copy"] is None
    assert (
        "::warning::No raw bucket this run (R2_ENDPOINT_URL, R2_RAW_BUCKET, R2_RAW_ACCESS_KEY_ID, "
        "R2_RAW_SECRET_ACCESS_KEY not set)" in capsys.readouterr().out
    )


def test_the_command_opens_the_bucket_with_the_raw_stores_key_and_never_the_public_one(monkeypatch):
    """publish.r2_client() falls back to the public bucket's key. The step
    never holds that key, and with both set here, this holds that the raw
    store's pair is the one passed."""
    settings = {
        "R2_ENDPOINT_URL": "https://r2.invalid",
        "R2_RAW_BUCKET": BUCKET,
        "R2_RAW_ACCESS_KEY_ID": "raw-id",
        "R2_RAW_SECRET_ACCESS_KEY": "raw-secret",
        "R2_ACCESS_KEY_ID": "public-id",
        "R2_SECRET_ACCESS_KEY": "public-secret",
    }
    for name, value in settings.items():
        monkeypatch.setenv(name, value)
    opened: dict = {}
    monkeypatch.setattr(publish.boto3, "client", lambda *_a, **kwargs: opened.update(kwargs) or object())

    copy, missing = fetch_planetiler_sources.raw_bucket_copy()

    assert missing == []
    assert copy.bucket == BUCKET
    assert (opened["endpoint_url"], opened["aws_access_key_id"], opened["aws_secret_access_key"]) == (
        "https://r2.invalid",
        "raw-id",
        "raw-secret",
    )


def test_the_command_prints_what_happened_to_the_others_before_it_fails(monkeypatch, capsys):
    def unavailable(*_args, **_kwargs):
        raise SourceUnavailable(
            "water_polygons: https://osmdata.openstreetmap.de/... could not be fetched",
            [Outcome("natural_earth", "uploaded", "434 bytes to the raw bucket, fetched 2026-11-04")],
        )

    monkeypatch.setattr(fetch_planetiler_sources, "ensure_sources", unavailable)

    assert fetch_planetiler_sources.main([]) == 1
    out = capsys.readouterr().out
    assert out.index("natural_earth: uploaded") < out.index("::error::Planetiler's profile sources are incomplete")


@pytest.mark.parametrize("action", ["bucket_unusable", "upload_failed"])
def test_the_command_warns_when_the_bucket_fails_and_still_succeeds(monkeypatch, capsys, action):
    monkeypatch.setattr(
        fetch_planetiler_sources, "ensure_sources", lambda *_a, **_k: [Outcome("raw_bucket", action, "ClientError: AccessDenied")]
    )

    assert fetch_planetiler_sources.main([]) == 0
    assert f"::warning::raw_bucket: {action} - ClientError: AccessDenied" in capsys.readouterr().out
