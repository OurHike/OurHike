"""Potomac Appalachian Trail Club: PATC's trails master, from its own ArcGIS Online organization.

Decision 54, wave 1: read live on 2026-10-03 (robots.txt first, lib/user_agent.py's agent, 2 s or more
between requests to one host) and registered in sources.json, where each row carries the count, extent,
statistics fingerprint, measured key, person fields and the item's own terms.

- `patc_trails_master`: PATC Trails Master, view (PATC). 2,101 lines, keyed on `GlobalID`.

The A.T. portion is LOADED via atc/; this layer carries the Tuscarora (about 230 mi by the coverage
audit), the Massanutten and the club's other trails, about 950 of the 1,190 miles PATC manages (Reasoned
by the audit from the club's stated mileage). Not landed: the older editions `PATC_Trails_2022` and
`PATC_All_Trails_2020`, which this view supersedes, and the organization's working layers (GPS ranger
tracks, relocation lines, buffers).
"""

from extract._kinds import arcgis_layer

CLAIMS = ("patc_trails_master",)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
