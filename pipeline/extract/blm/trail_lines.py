"""BLM's national "Trails Managed for Public", `BLM_Natl_GTLF_Public_Display/MapServer/7`.

19,532 features, no `editingInfo` and no date field (coverage audit
2026-10-01, batch b6_federal), so the change check answers UNKNOWN and the
layer is read whole every month. `ROUTE_PRMRY_NM` names 14,900 of them
(measured 2026-10-01; the registry row says there is no name field), and
10,224 are motorized with no exclusion declared (ORG_COVERAGE_SURVEY.md §3b).
The hosted twin below is the audit's suggested change marker: it is an ArcGIS
Online layer whose `dataLastEditDate` moves, which the on-prem one cannot
give.
"""

from datetime import date

from extract._contract import SameAs
from extract._kinds import arcgis_layer

CLAIMS = ("blm_trails",)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]

SAME_AS = (
    SameAs(
        original="blm_trails",
        copy=(
            "https://services1.arcgis.com/KbxwQRRfWyEYLgp4/arcgis/rest/services/BLM_Natl_GTLF_Public_Managed_Trails/FeatureServer/2",
        ),
        confirmed=date(2026, 10, 1),
        checked=(
            "returnCountOnly on both: 19,532 and 19,532",
            "count and max of ROUTE_PRMRY_NM on both: 14,900, 'Zippity Doo Da'; count of ADMIN_ST on both: 19,426",
            "the same 32 attribute columns; the copy adds only GlobalID, Original_GlobalID and Shape__Length",
        ),
    ),
)
