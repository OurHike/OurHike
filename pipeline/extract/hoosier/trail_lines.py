"""Hoosier Hikers Council: the Knobstone and Tecumseh trails it builds, in Indiana DNR's statewide trails
inventory.

Decision 54, wave 1: read live on 2026-10-03 (robots.txt first, lib/user_agent.py's agent, 2 s or more
between requests to one host) and registered in sources.json, where each row carries the count, extent,
statistics fingerprint, measured key, person fields and the item's own terms.

- `in_dnr_open_trails`: Indiana Trails Inventory, open trails (Indiana DNR). 5,496 lines, keyed on `globalid`.

Not landed: HHC's own `2023_TecumsehTrailTrack.gpx` (817,229 bytes, Last-Modified 2024-03-12, coverage
audit), a GPX file that wave 2's reader takes.
"""

from extract._kinds import arcgis_layer

CLAIMS = ("in_dnr_open_trails",)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
