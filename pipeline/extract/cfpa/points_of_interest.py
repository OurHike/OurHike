"""CFPA's Blue-Blazed Hiking Trail overnight sites and parking.

Read live 2026-10-03 for decision 54's wave 1. The coverage audit's older copy, CTTrailsMapData, was not
looked for again and is not noted here.
"""

from extract._kinds import arcgis_layer

CLAIMS = (
    "cfpa_overnight_sites",
    "cfpa_parking",
)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
