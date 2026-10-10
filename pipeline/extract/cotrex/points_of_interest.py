"""CPW's COTREX trailheads and facilities, layers 14 and 0 of CPWAdminData.

Read live 2026-10-03 for decision 54's wave 1. rmfi/ draws from the trailheads. CPWAdminData's other layers
were not read.
"""

from extract._kinds import arcgis_layer

CLAIMS = (
    "cotrex_trailheads",
    "cpw_facilities",
)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
