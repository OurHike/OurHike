"""Colorado Parks & Wildlife — COTREX: warnings, 2 ArcGIS layers extracted here (decision 53 phase B,
2026-10-03).

- `cpw_bear_conflict_areas`: CPW black bear human conflict areas, `CPWSpeciesData/FeatureServer/20`.
- `cpw_lion_conflict_areas`: CPW mountain lion human conflict areas,
  `CPWSpeciesData/FeatureServer/93`.

Both ride the type's lane, the notices job (decision 61). They were read monthly until review
finding ARC-1 of PR #1805 showed that neither could reach a phone that way: only the notices job's
models read them, and its warehouse never loads the monthly store.

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
    arcgis_layer("cpw_bear_conflict_areas"),
    arcgis_layer("cpw_lion_conflict_areas"),
]
