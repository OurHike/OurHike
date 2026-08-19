"""Tests for seed_spatial_extension.py - the offline spatial extension (#321).

The real extension is already installed wherever this suite runs (the whole
point of the script), so these use a stand-in file and a redirected home
rather than touching the developer's own `~/.duckdb`. What is exercised is the
part that can be silently wrong: where the file is written, and whether the
script notices when it has not achieved anything.
"""

from __future__ import annotations

import pathlib

import duckdb
import pytest

import seed_spatial_extension as seeder


@pytest.fixture
def home(tmp_path, monkeypatch):
    """A throwaway ~ so seeding never writes into the real extension dir."""
    monkeypatch.setattr(pathlib.Path, "home", classmethod(lambda cls: tmp_path))
    return tmp_path


def test_the_destination_is_keyed_by_duckdb_s_exact_version(home):
    """Extensions are ABI-locked, and DuckDB looks under the version it is.
    A path off by a version is one INSTALL silently ignores."""
    assert f"v{duckdb.__version__}" in str(seeder.destination())


def test_the_destination_uses_duckdb_s_own_platform_spelling(home):
    """Asked of DuckDB rather than derived from sys.platform: it encodes libc
    and architecture the way DuckDB spells them, and a near-miss produces a
    seeding that reports success and changes nothing."""
    platform = duckdb.connect().execute("PRAGMA platform").fetchone()[0]

    assert platform in str(seeder.destination())
    assert seeder.destination().name == seeder.EXTENSION_FILE


def test_seeding_copies_the_bundled_build_into_place(home, monkeypatch, tmp_path):
    source = tmp_path / "bundled" / seeder.EXTENSION_FILE
    source.parent.mkdir()
    source.write_bytes(b"not really an extension")
    monkeypatch.setattr(seeder, "bundled_extension", lambda: source)

    target = seeder.seed()

    assert target.read_bytes() == b"not really an extension"


def test_seeding_again_does_not_recopy_an_identical_file(home, monkeypatch, tmp_path):
    """Every web session runs this, and most of them find it already done."""
    source = tmp_path / "bundled" / seeder.EXTENSION_FILE
    source.parent.mkdir()
    source.write_bytes(b"payload")
    monkeypatch.setattr(seeder, "bundled_extension", lambda: source)
    target = seeder.seed()
    stamped = target.stat().st_mtime_ns

    assert seeder.seed().stat().st_mtime_ns == stamped


def test_a_target_of_a_different_size_is_replaced(home, monkeypatch, tmp_path):
    """The case that matters on a duckdb bump: something is already at the
    path and it is the wrong build."""
    source = tmp_path / "bundled" / seeder.EXTENSION_FILE
    source.parent.mkdir()
    source.write_bytes(b"the new build")
    monkeypatch.setattr(seeder, "bundled_extension", lambda: source)
    stale = seeder.destination()
    stale.parent.mkdir(parents=True)
    stale.write_bytes(b"old")

    assert seeder.seed().read_bytes() == b"the new build"


def test_a_missing_package_says_what_to_install_and_at_what_version(monkeypatch):
    """The failure a caller can act on. `distribution()` raising
    PackageNotFoundError on its own says only the name."""

    def absent(_name):
        raise seeder.PackageNotFoundError

    monkeypatch.setattr(seeder, "distribution", absent)

    with pytest.raises(SystemExit) as raised:
        seeder.bundled_extension()

    assert seeder.PACKAGE in str(raised.value)
    assert duckdb.__version__ in str(raised.value)


def test_a_distribution_without_the_extension_is_not_treated_as_seeded(monkeypatch):
    """A wheel that exists but carries no extension file - reporting success
    there would be the silent no-op this whole script exists to avoid."""

    class _Dist:
        version = "0.0.0"
        files = []

    monkeypatch.setattr(seeder, "distribution", lambda _name: _Dist())

    with pytest.raises(SystemExit, match=seeder.EXTENSION_FILE):
        seeder.bundled_extension()


def test_verify_actually_loads_the_extension_and_runs_a_spatial_call():
    """Not a mock: this is the check that separates "the copy happened" from
    "spatial works", and it is the only one that answers the real question."""
    seeder.verify()
