"""The Fish and Wildlife Service's refuge property points and access points, public views.

Read live 2026-10-03 for decision 54's wave 1. Both carry Public_Use, which a mart must filter on: the property
layer also holds sewage plants, fuel tanks and staff-only gates.
"""

from extract._kinds import arcgis_layer

CLAIMS = (
    "usfws_refuge_property_points",
    "usfws_refuge_access_points",
)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
