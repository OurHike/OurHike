"""PCTA's Halfmile water and campsite layers, and its current trailheads.

Read live 2026-10-03 for decision 54's wave 1. Halfmile's 2018 points are a survey, stale by design as
water. The other Halfmile_Point_2018 layers (gates, junctions, road crossings, stores, post offices,
lodging, food and a Notice layer) and Mountain_Passes are not extracted yet.
"""

from extract._kinds import arcgis_layer

CLAIMS = (
    "pcta_halfmile_water_sources",
    "pcta_halfmile_campsites",
    "pcta_trailheads",
)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
