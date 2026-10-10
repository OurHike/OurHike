"""UGRC's Utah trailheads, state park campsites and highest peaks.

Read live 2026-10-03 for decision 54's wave 1. wmc/ draws from the trailheads. SpringsNHDHighRes is NHD's
springs, USGS's data, and is not extracted here.
"""

from extract._kinds import arcgis_layer

CLAIMS = (
    "utah_trailheads",
    "utah_state_park_campsites",
    "utah_highest_peaks",
)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
