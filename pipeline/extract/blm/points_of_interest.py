"""BLM's national recreation sites, one layer for every type.

Read live 2026-10-03 for decision 54's wave 1. BLM_Natl_Recs_pts serves the same 10,241 rows again, all
in layer 23 and one type per layer in 0 to 22, which is a SAME_AS note below.
"""

from datetime import date

from extract._contract import SameAs
from extract._kinds import arcgis_layer

CLAIMS = ("blm_recreation_sites",)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]

SAME_AS = (
    SameAs(
        original="blm_recreation_sites",
        copy=("https://gis.blm.gov/arcgis/rest/services/recreation/BLM_Natl_Recs_pts/MapServer/23",),
        confirmed=date(2026, 10, 3),
        checked=(
            "'Recreation Locations - All' answers 10,241 rows, as BLM_Natl_Recreation/MapServer/3 does, with "
            "the same FET_TYPE counts (3: 2,984; 4: 1,727; 5: 1,411 and on) and the same fields bar GlobalID,"
            " which it carries as Original_GlobalID (read 2026-10-03). Its layers 0 to 22 are one per type, "
            "slices of the same rows (Potable Water 61, Group Shelter 36).",
        ),
    ),
)
