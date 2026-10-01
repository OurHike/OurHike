"""Finger Lakes Trail Conference: closures, published, and not landed (coverage audit 2026-10-01, batch
c4_regional_1).

A structured feed. The closure label is free text (40 "CLOSED", plus "Logging", "Beaver dam has
flooded the trail.", …), so poll 7's `obstructs_trail` mapping is needed.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`https://fingerlakestrail.org/FLTC/new_notice/noticesJSON.php?data=notices` is JSON. It needs only the"
        " PHPSESSID cookie the public page sets; there is no login. 713 notices run from 2004-11-01 to "
        '2026-09-26; 121 active, 9 active with `tn_Closure` (e.g. 2026-09-07 "Trail Closed: Storm Damage, River'
        ' Rd to Portageville"). Fields: `tn_Hunting`, `tn_tempNotice`, `tn_Expire`, `tn_tmid` (map id; '
        '`?data=maps` returns 62 maps). Also ArcGIS `Closures_/FeatureServer/0` ("Hunting and high water '
        'closures": 82 lines) and `Temporary_Notices/FeatureServer/14` (28 points, lastEdit 2026-09-26).',
    ),
    where=(
        "https://fingerlakestrail.org/FLTC/new_notice/noticesJSON.php?data=notices",
        "https://services7.arcgis.com/GwV4OWqOyYWWUpBK/arcgis/rest/services/Closures_/FeatureServer/0",
        "https://services7.arcgis.com/GwV4OWqOyYWWUpBK/arcgis/rest/services/Temporary_Notices/FeatureServer/14",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
