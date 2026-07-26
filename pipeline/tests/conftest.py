"""Shared fixtures for the pipeline test suite.

Fixtures generate tiny synthetic geometries/rasters programmatically rather
than committing binary sample files - partly for git hygiene, partly because
a fixture that builds its own "corrupted" TIFF byte-for-byte is self-
documenting about what "corrupted" means, instead of relying on an opaque
checked-in blob. See ../../TESTING.md for the philosophy this follows.
"""
