"""Shared fixtures for the pipeline test suite.

Fixtures generate tiny synthetic geometries/rasters programmatically rather
than committing binary sample files - partly for git hygiene, partly because
a fixture that builds its own "corrupted" TIFF byte-for-byte is self-
documenting about what "corrupted" means, instead of relying on an opaque
checked-in blob. See ../../TESTING.md for the philosophy this follows.
"""

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

    `reference/trail_water.json` is checked in, and unify_all_sources reads
    it - so without this a suite of six synthetic points near (-74, 41)
    quietly gains seventeen real stream crossings from the Hudson Highlands,
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
