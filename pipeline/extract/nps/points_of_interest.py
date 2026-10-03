"""The Great Smokies' backcountry shelters, with the park's own capacities.

Read live 2026-10-03 for decision 54's wave 1. NPS's nationwide point layer, NPS_Public_POIs, is its
own trail_orgs.json row, nps-poi, and is extracted once there, in nps_poi/points_of_interest.py.
"""

from extract._kinds import arcgis_layer

CLAIMS = ("nps_grsm_backcountry_shelters",)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
