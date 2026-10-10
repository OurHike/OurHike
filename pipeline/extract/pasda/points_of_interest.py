"""PA DCNR's point layers on its own server and PASDA's: state park buildings, state forest campsites, Explore PA Trails access points, park amenities and geoheritage features.

Read live 2026-10-03 for decision 54's wave 1. The buildings layer is an insurance inventory, so its rows
list the reviewers' and submitters' columns that never load. laurel/ draws its shelters from it.
"""

from extract._kinds import arcgis_layer

CLAIMS = (
    "pasda_state_park_buildings",
    "pasda_state_forest_campsites",
    "pasda_explore_pa_trail_access",
    "pasda_state_park_amenities",
    "pasda_geoheritage_features",
)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
