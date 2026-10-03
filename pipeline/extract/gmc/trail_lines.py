"""Green Mountain Club: the Long Trail system, TRAIL_MASTER, from GMC's ArcGIS Online organization.

Decision 54, wave 1: read live on 2026-10-03 (robots.txt first, lib/user_agent.py's agent, 2 s or more
between requests to one host) and registered in sources.json, where each row carries the count, extent,
statistics fingerprint, measured key, person fields and the item's own terms.

- `gmc_trail_master`: Long Trail system, TRAIL_MASTER (GMC). 403 lines, keyed on `GlobalID`.

The A.T.'s stretch with the Long Trail is LOADED via atc/; this layer is GMC's own line of it and of the
Long Trail north of Maine Junction, which no loaded row carried. Not landed: `TRAIL_MASTER_DayHikes`
(362 rows of the same schema plus DayHikeID columns, last edited 2026-04-13), a suggested_hikes input
rather than a trail-line dataset, and `ProjectPlanning_DataCollectionLines`, a working layer.
MileMarkers_LT is a points layer.
"""

from extract._kinds import arcgis_layer

CLAIMS = ("gmc_trail_master",)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
