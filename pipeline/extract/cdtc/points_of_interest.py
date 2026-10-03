"""CDTC's water caches, parking and trailhead waypoints.

Read live 2026-10-03 for decision 54's wave 1. CDTC's NPS campsite and point-of-interest views carry
NPS_Public_POIs' own columns, so they are SAME_AS notes on nps_points_of_interest (nps_poi/). Its
Post_Office_view carries USGS's structures schema and is not extracted here.
"""

from datetime import date

from extract._contract import SameAs
from extract._kinds import arcgis_layer

CLAIMS = (
    "cdtc_water_caches",
    "cdtc_bootheel_water_caches",
    "cdtc_parking",
    "cdtc_trailheads_and_mail",
)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]

SAME_AS = (
    SameAs(
        original="nps_points_of_interest",
        copy=(
            "https://services8.arcgis.com/WyuHwdftppQLa5KO/arcgis/rest/services/Camping_view/FeatureServer/1",
            "https://services8.arcgis.com/WyuHwdftppQLa5KO/arcgis/rest/services/NPS_Points_of_Interest_view/FeatureServer/1",
            "https://services8.arcgis.com/WyuHwdftppQLa5KO/arcgis/rest/services/2026_NPS_Campsites_view/FeatureServer/1",
            "https://services8.arcgis.com/WyuHwdftppQLa5KO/arcgis/rest/services/NPS_Campsites_view/FeatureServer/1",
        ),
        confirmed=date(2026, 10, 3),
        checked=(
            "Camping_view carries NPS_Public_POIs' own columns (POINAME, MAPLABEL, POITYPE, UNITNAME, "
            "SEASONAL, SEASDESC) and 420 rows, all Campsite or Campground in Yellowstone, Glacier and Rocky "
            "Mountain, where NPS publishes 1,020 of those types (returnCountOnly, 2026-10-03): a corridor "
            "subset of NPS's points, not a survey of CDTC's own. NPS_Points_of_Interest_view is the same "
            "columns, 742 rows in four parks, POITYPE suffixed ' 1'. Reasoned from the columns and counts; no"
            " row was matched to NPS's. The coverage audit read the 2026 and older NPS campsite views as "
            "copies of NPS data too.",
        ),
    ),
)
