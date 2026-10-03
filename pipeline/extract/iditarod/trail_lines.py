"""Iditarod Historic Trail Alliance: trail lines, drawn from blm/'s resources (decision 34), registered on
2026-10-03.

Winter trail. The Alliance's `plan-your-trip.html`: "primarily a winter trail and many sections of
the Trail are barely usable in the summer." Much of the route crosses frozen rivers and wetland. A
summer hiker reading it as a path is in danger. It needs a seasonal flag before it draws

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Live read 2026-10-03 (decision 54, wave 1): `blm_iditarod_nht` (26 lines) registered in "
        "sources.json and extracted in blm/trail_lines.py. A winter trail: its row's notes carry the "
        "danger to a summer hiker.",
        "`NPSAGOL/Iditarod_National_Historic_Trail_BLM_Official_Temp/FeatureServer/0`: 26 named segments "
        "(Seward to Portage … Safety to Nome), edited 2023-04-03, owner a personal ArcGIS account, credit"
        ' "a named individual - Bureau of Land Management", licence "Should provide/reference '
        "'supplemental information' when data is presented or published\". `blm_trails` (the `via` row) "
        'has 0 Iditarod rows. `alaska_trails` (LOADED) has 12 Iditarod-named features ("Iditarod '
        '(Historic)", "INHT: GIRDWOOD IDITAROD TRAIL" …). Own: none. `trail-map.html` is a static image, '
        "plus an Esri MapJournal (`appid=625b0b94…`)",
    ),
    where=(
        "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services/Iditarod_National_Historic_Trail_BLM_Official_Temp/FeatureServer/0",
    ),
    reason="drawn from blm/'s resources, extracted once there (decision 34); checked names the layer this org's data arrives in",
)
