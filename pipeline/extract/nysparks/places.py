"""OPRHP's park polygons, `NYS_Park_Polygons/0`, which export_places.py reads as `PARKS_KEY`.

858 polygons, last edited 2026-08-21 (coverage audit 2026-10-01, batch
b4_oprhp_mohonk_gatc). Not landed: `Regions/0` (13), `ParkPoints/0` (262, with
`Facility_URL`), the heritage-area layers, and
`NY_State_Park_Properties_by_County_(public_view)/0` (312). Nor, from the
Empire State Trail (the coverage audit's `empire-state-trail` candidate, which
decision 54's wave 6 folds into this folder on 2026-10-08):
`Attractions_Public/0` (177 attractions), the 61 legs EST_Public's ESTLeg
names, and Parks & Trails New York's trail-town business listings, which wait
on a row of PTNY's own.
"""

from extract._kinds import arcgis_layer

CLAIMS = ("oprhp_park_polygons",)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
