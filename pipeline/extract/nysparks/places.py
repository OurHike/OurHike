"""OPRHP's park polygons, `NYS_Park_Polygons/0`, which export_places.py reads as `PARKS_KEY`.

858 polygons, last edited 2026-08-21 (coverage audit 2026-10-01, batch
b4_oprhp_mohonk_gatc). Not landed: `Regions/0` (13), `ParkPoints/0` (262, with
`Facility_URL`), the heritage-area layers, and
`NY_State_Park_Properties_by_County_(public_view)/0` (312).
"""

from extract._kinds import arcgis_layer

CLAIMS = ("oprhp_park_polygons",)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
