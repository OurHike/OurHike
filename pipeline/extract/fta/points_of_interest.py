"""FTA's campsite and trailhead layers.

Read live 2026-10-03 for decision 54's wave 1. FTA publishes no water layer; its campsites' Dist2Water_ft
is the distance to water, never a source.
"""

from extract._kinds import arcgis_layer

CLAIMS = (
    "fta_campsites",
    "fta_trailheads",
)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
