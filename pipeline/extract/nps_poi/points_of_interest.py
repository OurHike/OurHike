"""NPS's nationwide public points of interest.

Read live 2026-10-03 for decision 54's wave 1. Held on scope by trail_orgs.json's nps-poi row (a corridor
clip and a POITYPE allowlist a person reads), which decides publication, not extraction. Natchez Trace,
E Mau Na Ala Hele and CDTC's NPS views draw from this resource. The Geographic MapServer serves the same
rows again, a SAME_AS note below.
"""

from datetime import date

from extract._contract import SameAs
from extract._kinds import arcgis_layer

CLAIMS = ("nps_points_of_interest",)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]

SAME_AS = (
    SameAs(
        original="nps_points_of_interest",
        copy=("https://mapservices.nps.gov/arcgis/rest/services/NationalDatasets/NPS_Public_POIs_Geographic/MapServer/0",),
        confirmed=date(2026, 10, 3),
        checked=(
            "the Geographic MapServer answers the same 35,639 rows with the same 37 fields as "
            "NPS_Public_POIs/FeatureServer/0 (returnCountOnly and metadata, read 2026-10-03), the same data "
            "in geographic coordinates. GEOMETRYIDs were not matched row by row.",
        ),
    ),
)
