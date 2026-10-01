"""Mid State Trail Association (PA): trail lines, drawn from another folder's resource (coverage audit
2026-10-01, batch c4_regional_1).

The steward's 204 segments against PASDA's 3 is a #1709 dual-source pair.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`pasda_dcnr_trails`: 3 features matching `NAME01 LIKE '%MID STATE%'`, re-measured today. MSTA's own: "
        'ArcGIS `gishikemstorg` "2022_12_31 mst_main", '
        "`https://services6.arcgis.com/DtSEkvbAjAfDY35J/arcgis/rest/services/2022_12_31_mst_main/FeatureServer/0`."
        " 204 polylines with Region, Section, Type, Ownership; lastEdit 2023-01-07.",
    ),
    where=("https://services6.arcgis.com/DtSEkvbAjAfDY35J/arcgis/rest/services/2022_12_31_mst_main/FeatureServer/0",),
    reason="drawn from pasda/'s resources, extracted once there (decision 34); checked names the layer this org's data"
    " arrives in",
)
