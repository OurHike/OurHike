"""The Bay Area Ridge Trail Council's campsite layer.

Read live 2026-10-03 for decision 54's wave 1. Its STATUS is 2023's and is never read as live.
"""

from extract._kinds import arcgis_layer

CLAIMS = ("ridgetrail_campsites",)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
