"""SBTS's Connected Communities trailhead inventory, a planning layer.

Read live 2026-10-03 for decision 54's wave 1. Its comments, which name a person, never load.
"""

from extract._kinds import arcgis_layer

CLAIMS = ("sbts_connected_community_trailheads",)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
