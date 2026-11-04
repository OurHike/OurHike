"""Tests for lib/planetiler_sources.py and fetch_planetiler_sources.py (#1970).

Every download here is a fake that writes a small zip archive, so nothing
reaches a network. What these pin is the decision per source: keep, fetch,
or keep an older copy, and that the run fails only when a source has no copy
at all.
"""

from __future__ import annotations

import io
import json
import zipfile
from datetime import date, timedelta
from pathlib import Path

import pytest
import requests

import fetch_planetiler_sources
from lib.planetiler_sources import (
    MANIFEST_NAME,
    MAX_AGE_DAYS,
    SOURCES,
    SOURCES_DIR,
    Outcome,
    SourceUnavailable,
    ensure_sources,
    github_output_marker,
    planetiler_args,
)

TODAY = date(2026, 11, 4)


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
    was on 2026-11-03: there is no copy to fall back on, so the run fails,
    in this step, seconds in. The other two still land and are reported, so
    the save step keeps them and the next run asks only for the water."""
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
