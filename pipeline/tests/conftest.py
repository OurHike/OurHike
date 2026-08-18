"""Shared fixtures for the pipeline test suite.

Fixtures generate tiny synthetic geometries/rasters programmatically rather
than committing binary sample files - partly for git hygiene, partly because
a fixture that builds its own "corrupted" TIFF byte-for-byte is self-
documenting about what "corrupted" means, instead of relying on an opaque
checked-in blob. See ../../TESTING.md for the philosophy this follows.
"""

import socket

import duckdb
import pytest

import export_poi
from lib import fetch_receipts


@pytest.fixture(autouse=True)
def receipts_in_a_tmp_dir(tmp_path, monkeypatch):
    """Keep fetch receipts (#542) out of the real data/ tree.

    Every fetcher's main() now ends by recording one, and several tests drive
    a real main() with its OUT_PATH redirected to tmp_path. Without this the
    suite would write into pipeline/data/raw/receipts/ on a developer's
    machine - and worse, a later run of check_output_quality.py against real
    data would find receipts describing files a test wrote, which is exactly
    the "believed a record nobody should have trusted" failure the receipt is
    supposed to prevent.

    Autouse rather than opt-in because the tests that trigger it are the ones
    that do not mention receipts at all - a test author adding a new
    main()-driving test has no reason to know this is needed.

    An absolute path here wins over the module's relative default, because
    receipts_dir() joins it onto the pipeline root and pathlib's `/` keeps an
    absolute right-hand side."""
    monkeypatch.setattr(fetch_receipts, "RECEIPTS_DIR", tmp_path / "receipts")


@pytest.fixture(autouse=True)
def no_real_trail_water(tmp_path, monkeypatch):
    """Keep the real corridor's water out of every synthetic fixture (#529).

    `data/raw/trail_water.json` sits on any machine that has run the fetch,
    and unify_all_sources reads it - so without this a suite of six synthetic
    points near (-74, 41) quietly gains seventeen real stream crossings from
    the Hudson Highlands,
    which is TESTING.md's "never the real data" rule broken by a file the
    test never mentions.

    Autouse and in conftest rather than in the one suite that noticed,
    because the tests it protects are the ones with no reason to know: the
    failure landed in test_fetch_poi_images.py, whose subject is the Commons
    crawl and which calls unify_all_sources only to derive the ids the export
    will write. A test author adding another caller has the same blind spot.

    The capacity, water-distance and photo files need no equivalent: those
    are read in main(), which every test that drives it already redirects.
    This one is read during unification itself, which is the whole reason it
    reaches further than its own suite.
    """
    monkeypatch.setattr(export_poi, "TRAIL_WATER_PATH", tmp_path / "no-trail-water.json")


def spatial_connection() -> "duckdb.DuckDBPyConnection":
    """One home for the DuckDB spatial setup six test files used to repeat
    byte-for-byte (#324). A plain function rather than only a fixture, so the
    handful of tests that build a connection mid-test (rather than taking one
    as an argument) share the same line too."""
    connection = duckdb.connect()
    connection.execute("INSTALL spatial; LOAD spatial;")
    return connection


@pytest.fixture
def spatial_con():
    """A spatial-enabled DuckDB connection, closed after the test."""
    connection = spatial_connection()
    yield connection
    connection.close()


@pytest.fixture(autouse=True)
def no_outside_network(monkeypatch):
    """Make TESTING.md's "any unmocked request raises" structurally true (#324).

    It used to hold only inside tests that requested `requests_mock` - nothing
    stopped a new test from quietly reaching the wire. This blocks every
    Python-level socket connection to a non-loopback address; requests_mock
    keeps working because it intercepts at the adapter layer, above sockets,
    and loopback stays open for the tests that stand up a real local server
    (test_serve_processed.py).

    Deliberately Python-level only: DuckDB's `INSTALL spatial` fetches its
    extension through native code on a fresh CI machine, below this guard's
    reach, and that one documented network call is the environment's to
    manage (see .claude/hooks/session-start.sh and TESTING.md's caveat).
    """
    real_connect = socket.socket.connect

    def guarded(self, address, *args, **kwargs):
        host = address[0] if isinstance(address, tuple) else address
        if isinstance(host, str) and (host in ("127.0.0.1", "::1", "localhost") or isinstance(address, str)):
            return real_connect(self, address, *args, **kwargs)
        raise RuntimeError(
            f"Test tried to open a real network connection to {address!r}. "
            "Mock it (requests_mock) instead - TESTING.md: tests never touch "
            "the network."
        )

    monkeypatch.setattr(socket.socket, "connect", guarded)
