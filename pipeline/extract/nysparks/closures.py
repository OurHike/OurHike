"""OPRHP's temporary trail closures, `NY_State_Parks_Temporary_Trail_Closure/0`. Hourly, as every closure is.

4 polygons, last edited 2026-06-16 (coverage audit 2026-10-01, batch
b4_oprhp_mohonk_gatc). The layer is a subset of OPRHP's own alerts:
ALERTS_NOTICES_SURVEY.md §3b found Lake Awosting closed on parks.ny.gov and
absent here. So a zero from this layer says the layer is empty, never that
nothing in a state park is closed, and the count proving it is the server's
own `returnCountOnly`. The layer's own item carries an empty `licenseInfo`
(ORG_COVERAGE_SURVEY.md §3b). Not landed: `EST_Public/5` `UnderConstruction`,
2 work-zone polygons.
"""

from extract._kinds import arcgis_layer

CLAIMS = ("oprhp_trail_closures",)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
