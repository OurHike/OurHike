"""The Sturgis local trail system's trailheads and parking, which Black Hills Trails publishes with the City of Sturgis.

Read live 2026-10-03 for decision 54's wave 1. The same org's TrailData service is an older copy (the coverage
audit counted 2 trailheads and 2 parking) and was not read again.
"""

from extract._kinds import arcgis_layer

CLAIMS = (
    "black_hills_trailheads",
    "black_hills_parking",
)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
