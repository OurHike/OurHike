"""IATA's water, camping and parking layers, the bases its public views are cut from.

Read live 2026-10-03 for decision 54's wave 1. The views are SAME_AS notes below. IAT_Water's own
description says 'some points should not be shared publicly', which sources.json's iata_water row
quotes and sends to the maintainer. The hunting-closure layers on the same org (IAT_Hunting_Closures
and two siblings) are closures, decision 53's; IAT_PrimitiveCamping is 39 polygons, an area rather
than a point, and is not extracted here.
"""

from datetime import date

from extract._contract import SameAs
from extract._kinds import arcgis_layer

CLAIMS = (
    "iata_water",
    "iata_camping",
    "iata_parking",
)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]

SAME_AS = (
    SameAs(
        original="iata_water",
        copy=(
            "https://services.arcgis.com/EeCmkqXss9GYEKIZ/arcgis/rest/services/IAT_Potable_Water/FeatureServer/0",
            "https://services.arcgis.com/EeCmkqXss9GYEKIZ/arcgis/rest/services/IAT_Possible_Water/FeatureServer/0",
        ),
        confirmed=date(2026, 10, 3),
        checked=(
            "each item's relatedItems (Service2Service, reverse) names 'IAT - Water Features', item "
            "ac9f90ddfd3d4292b97f7a2f58c94e3b, as its source, and each answers the same 423 rows with the "
            "same six fields (read 2026-10-03). The 'Potable Water' view is not filtered to potable water: "
            "its 423 include the 217 coded Treatment required.",
        ),
    ),
    SameAs(
        original="iata_camping",
        copy=(
            "https://services.arcgis.com/EeCmkqXss9GYEKIZ/arcgis/rest/services/IAT_-_Camping_view/FeatureServer/0",
            "https://services.arcgis.com/EeCmkqXss9GYEKIZ/arcgis/rest/services/IAT_Backpack_Campsite/FeatureServer/0",
            "https://services.arcgis.com/EeCmkqXss9GYEKIZ/arcgis/rest/services/IAT_Car_Camping/FeatureServer/0",
            "https://services.arcgis.com/EeCmkqXss9GYEKIZ/arcgis/rest/services/IAT_Dispersed_Camping_Areas_(DCAs)/FeatureServer/0",
        ),
        confirmed=date(2026, 10, 3),
        checked=(
            "each item's relatedItems (Service2Service, reverse) names 'IAT - Camping', item "
            "6ef656ba224c4d469184d002d462a013, as its source, and their counts, 14 + 33 + 161 + 39, sum to "
            "that layer's 247, the same nine fields on each (read 2026-10-03): filtered views of "
            "iata_camping.",
        ),
    ),
)
