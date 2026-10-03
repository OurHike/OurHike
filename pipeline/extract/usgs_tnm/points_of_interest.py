"""The National Map's structures (campgrounds, trailheads, cabins, shelters, ranger stations) and GNIS's named springs.

Read live 2026-10-03 for decision 54's wave 1. A GNIS spring is a name on a map, never a report of water.
The structures are a compilation of other agencies' points, so they overlap layers registered elsewhere
and are deduplicated in dbt.
"""

from extract._kinds import arcgis_layer

CLAIMS = (
    "usgs_structures_campgrounds",
    "usgs_structures_trailheads",
    "usgs_structures_cabins",
    "usgs_structures_shelters",
    "usgs_structures_ranger_stations",
    "usgs_gnis_springs",
)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
