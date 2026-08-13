"""Shared fixtures for the pipeline test suite.

Fixtures generate tiny synthetic geometries/rasters programmatically rather
than committing binary sample files - partly for git hygiene, partly because
a fixture that builds its own "corrupted" TIFF byte-for-byte is self-
documenting about what "corrupted" means, instead of relying on an opaque
checked-in blob. See ../../TESTING.md for the philosophy this follows.
"""

import pytest

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
