"""Colorado Parks & Wildlife — COTREX: warnings, 2 ArcGIS layers extracted here (decision 53 phase B,
2026-10-03).

- `cpw_bear_conflict_areas`: CPW black bear human conflict areas, `CPWSpeciesData/FeatureServer/20`.
  Read monthly, not on the type's lane: a standing conflict-area map (lastEditDate 2026-05-07),
  whose hundreds of polygons are too large a first read for the hourly lane's 150 s budget.
- `cpw_lion_conflict_areas`: CPW mountain lion human conflict areas,
  `CPWSpeciesData/FeatureServer/93`. Read monthly, not on the type's lane: a standing conflict-area
  map (lastEditDate 2026-05-07), whose hundreds of polygons are too large a first read for the
  hourly lane's 150 s budget.

Each layer's row in sources.json holds its counts, dates, terms and the person fields it never
loads. Change checks are _kinds.py's ArcgisLayer: a conditional GET of the layer document on ArcGIS
Online, the statistics fingerprint on an on-prem server, and an allowed zero only beside the
server's own returnCountOnly read in the same run.

Read and not wired (decision 53 phase B, 2026-10-03): https://cpw.state.co.us/hunting/big-game (now
/activities/hunting/big-game) and https://cpw.state.co.us/living-bears, evergreen guidance pages
(JSON-LD dateModified 2026-09-29 and 2026-08-14), not notices; season dates are in brochures.
"""

from extract._kinds import arcgis_layer

CLAIMS = ("cpw_bear_conflict_areas", "cpw_lion_conflict_areas")
RESOURCES = [
    arcgis_layer(
        "cpw_bear_conflict_areas",
        cadence_override="monthly",
        cadence_reason="a standing conflict-area map (lastEditDate 2026-05-07), whose hundreds of polygons are too large a first read for the hourly lane's 150 s budget",
    ),
    arcgis_layer(
        "cpw_lion_conflict_areas",
        cadence_override="monthly",
        cadence_reason="a standing conflict-area map (lastEditDate 2026-05-07), whose hundreds of polygons are too large a first read for the hourly lane's 150 s budget",
    ),
]
