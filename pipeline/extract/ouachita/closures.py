"""Friends of the Ouachita Trail: closures, published, and not landed (coverage audit 2026-10-01, batch
p05_persist).

USFS: public domain. Arkansas.com is JSON but not GIS, and I read no terms (@unvalidated); decision
21(a) does not reach it (Reasoned). Folders `usfs/` and `arkansas-parks/` (the slug c19 proposes).
FoOT's own condition sheet stays the OT-specific channel, and a closure there would arrive as a …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "(a) `https://www.fs.usda.gov/r08/ouachita/alerts` (HTML) has 23 alerts. Trail closures elsewhere on "
        'the forest: "Hole in the Ground Hiking Trail Closed due to Logging Operations" (2026-08-25); "Sugar '
        'Creek Multi-Use Trail Partially Closed" (3.1 mi, 2026-08-10); "Lake Ouachita Vista Trail Partially '
        'Closed for Timber Sale Activity"; "Portions of Wildcat Trail Closed Due to Tornado Damage". There is '
        'also "Forest Order- Trails" (#OA-ONF-06-2026), and washouts close roads FSR W15 and CO2E on the '
        'Caddo-Womble district (2026-09-28, "still open to foot traffic"). None names the Ouachita Trail. No …',
    ),
    where=(
        "https://www.fs.usda.gov/r08/ouachita/alerts",
        "https://gis.arkansas.gov/arcgis/rest/services",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
