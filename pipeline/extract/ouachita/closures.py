"""Friends of the Ouachita Trail: closures, drawn from usfs/closures.py's Ouachita National Forest alerts page
(decision 53 phase B, 2026-10-03).

The Ouachita National Forest's alerts page is the Forest Service's, so it lands once, in usfs/closures.py
as `usfs_r08_ouachita_alerts` (decision 34). FoOT's own channels carry warnings rather than closures
(warnings.py: the condition sheet and the Hiker Alert PDF). Arkansas State Parks' JSON is not GIS and
no terms were read for it (the coverage audit), so it is not registered.

Before decision 53 phase B this file was the coverage audit's note (confirmed 2026-10-01, batch
p05_persist), whose `checked` is kept below.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 3),
    checked=(
        "usfs/closures.py `usfs_r08_ouachita_alerts` reads https://www.fs.usda.gov/r08/ouachita/alerts (decision "
        "53 phase B, 2026-10-03): 23 alert cards, critical 4, caution 5, information 14.",
        "(coverage audit, 2026-10-01) (a) `https://www.fs.usda.gov/r08/ouachita/alerts` (HTML) has 23 alerts. Trail "
        'closures elsewhere on the forest: "Hole in the Ground Hiking Trail Closed due to Logging Operations" '
        '(2026-08-25); "Sugar Creek Multi-Use Trail Partially Closed" (3.1 mi, 2026-08-10); "Lake Ouachita Vista '
        'Trail Partially Closed for Timber Sale Activity"; "Portions of Wildcat Trail Closed Due to Tornado '
        'Damage". There is also "Forest Order- Trails" (#OA-ONF-06-2026), and washouts close roads FSR W15 and '
        'CO2E on the Caddo-Womble district (2026-09-28, "still open to foot traffic"). None names the Ouachita '
        "Trail. No …",
    ),
    where=(
        "https://www.fs.usda.gov/r08/ouachita/alerts",
        "https://gis.arkansas.gov/arcgis/rest/services",
    ),
    reason="drawn from usfs/'s resources, extracted once there (decision 34); checked names the page this org's closures arrive in",
)
