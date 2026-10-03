"""Trailkeepers of Oregon: the Oregon Coast Trail's route and its gaps, from a 2022 gap analysis on TKO's
ArcGIS Online organization.

Decision 54, wave 1: read live on 2026-10-03 (robots.txt first, lib/user_agent.py's agent, 2 s or more
between requests to one host) and registered in sources.json, where each row carries the count, extent,
statistics fingerprint, measured key, person fields and the item's own terms.

- `tko_oregon_coast_trail`: Oregon Coast Trail route and gaps, 2022 (Trailkeepers of Oregon). 204 lines, keyed on geometry + `TrailType`.

The GAP rows are road walks and must not draw as trail; the row's notes carry the counts.
"""

from extract._kinds import arcgis_layer

CLAIMS = ("tko_oregon_coast_trail",)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
