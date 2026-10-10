"""NC DPR's state park points, one per park office.

Read live 2026-10-03 for decision 54's wave 1. The office phone number is never asked for.
"""

from extract._kinds import arcgis_layer

CLAIMS = ("nc_state_parks_points",)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
