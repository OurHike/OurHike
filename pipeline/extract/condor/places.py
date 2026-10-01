"""Condor Trail Association: places, published, and not landed (coverage audit 2026-10-01, batch
p10_persist).

USFS copyrightText "US Forest Service Enterprise Map Services Program": public domain, federal.
ForestWatch item: licenseInfo empty, so none_stated, but it is third-party: it should not stand in
for the closure order's own map (Exhibit B), which is a PDF (Reasoned). Folder: `usfs/`.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`EDW_ForestSystemBoundaries_01/MapServer/0` forestorgcode '0507': 1 polygon (1,970,265 ac). "
        "`EDW_Wilderness_02/MapServer/0`: Sespe (219,548 ac), Matilija, Dick Smith, San Rafael, Garcia, "
        "Machesna Mountain, Santa Lucia, Silver Peak, Ventana (236,192 ac) and Chumash, 1 polygon each. The "
        "Sespe Condor Sanctuary, which a current closure order names, exists as a polygon only in "
        "`ForestWatchGIS` `Sespe_Condor_Sanctuary/FeatureServer` (item `fbd369f3cfcb4148affedd995da97a76`, an "
        "advocacy NGO, 2023-11-03). The three EDW special-area services hold no condor row. The USFS trailheads"
        " (39) are a trailhead …",
    ),
    where=("https://services9.arcgis.com/olCAyDMW794Lg7Au/arcgis/rest/services/Sespe_Condor_Sanctuary/FeatureServer",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
