"""Alaska Trails' cabins and campsites, and its access points, for the Alaska Long Trail.

Read live 2026-10-03 for decision 54's wave 1. The regional services are filtered views of these two,
SAME_AS notes below. A Proposed access point must never render as one a hiker can use.
"""

from datetime import date

from extract._contract import SameAs
from extract._kinds import arcgis_layer

CLAIMS = (
    "alaska_trails_cabins_and_campsites",
    "alaska_trails_access_points",
)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]

SAME_AS = (
    SameAs(
        original="alaska_trails_cabins_and_campsites",
        copy=(
            "https://services.arcgis.com/E4aLbdRuC2azR6Sw/arcgis/rest/services/Seward_to_Girdwood_Camping_Infrastructure/FeatureServer/10",
            "https://services.arcgis.com/E4aLbdRuC2azR6Sw/arcgis/rest/services/Anchorage_Region_Camping_Infrastructure/FeatureServer/10",
            "https://services.arcgis.com/E4aLbdRuC2azR6Sw/arcgis/rest/services/Eagle_River_to_Cantwell_Camping_Infrastructure/FeatureServer/10",
            "https://services.arcgis.com/E4aLbdRuC2azR6Sw/arcgis/rest/services/Denali_Region_Camping_Infrastructure/FeatureServer/10",
            "https://services.arcgis.com/E4aLbdRuC2azR6Sw/arcgis/rest/services/Fairbanks_Regin_Camping_Infrastructure/FeatureServer/10",
        ),
        confirmed=date(2026, 10, 3),
        checked=(
            "regional services whose layer 10 is named Campsites_and_Cabins like the original's; the Seward "
            "to Girdwood item's relatedItems (Service2Service, reverse) names 'AKLT Cabins and Campsites', "
            "item a0e62564b3574eb5af96e49448609e09, and it answered 37 of the original's 108 rows (read "
            "2026-10-03). The other four were not opened.",
        ),
    ),
    SameAs(
        original="alaska_trails_access_points",
        copy=(
            "https://services.arcgis.com/E4aLbdRuC2azR6Sw/arcgis/rest/services/Seward_to_Girdwood_Access_Points/FeatureServer/12",
            "https://services.arcgis.com/E4aLbdRuC2azR6Sw/arcgis/rest/services/Anchorage_Region_Access_Points/FeatureServer/12",
            "https://services.arcgis.com/E4aLbdRuC2azR6Sw/arcgis/rest/services/Eagle_River_to_Cantwell_Access_Points/FeatureServer/12",
            "https://services.arcgis.com/E4aLbdRuC2azR6Sw/arcgis/rest/services/Denali_Region_Access_Points/FeatureServer/12",
            "https://services.arcgis.com/E4aLbdRuC2azR6Sw/arcgis/rest/services/Fairbanks_Region_Access_Points/FeatureServer/12",
        ),
        confirmed=date(2026, 10, 3),
        checked=(
            "regional services whose layer 12 is named AccessPoints like the original's; the Seward to "
            "Girdwood item's relatedItems names 'AccessPoints', item 578431133a7749dcb007ec0effa6b8e9, and it"
            " answered 25 of the original's 183 rows (read 2026-10-03). The other four were not opened.",
        ),
    ),
)
