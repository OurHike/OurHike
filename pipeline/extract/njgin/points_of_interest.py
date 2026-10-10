"""NJDEP's state-owned open space points of interest.

Read live 2026-10-03 for decision 54's wave 1. Under the NJDEP Data Distribution Agreement, whose
conditions travel with the layer. The hosted twin is a SAME_AS note below.
"""

from datetime import date

from extract._contract import SameAs
from extract._kinds import arcgis_layer

CLAIMS = ("nj_open_space_points_of_interest",)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]

SAME_AS = (
    SameAs(
        original="nj_open_space_points_of_interest",
        copy=(
            "https://services1.arcgis.com/QWdNfRs7lkPq4g4Q/arcgis/rest/services/Open_Space__State_Owned__Points_of_Interest_h/FeatureServer/62",
        ),
        confirmed=date(2026, 10, 3),
        checked=(
            "the hosted twin answers the same 3,260 rows, GLOBALID unique on both (3,260 of 3,260), with the "
            "on-prem layer's 23 attribute fields plus five (OSOURCE, OSRCE_TYPE, ODATE, SOURCE, COMMENTS) (read "
            "2026-10-03). GLOBALIDs were not matched row by row.",
        ),
    ),
)
