"""Ice Age Trail Alliance: closures, published, and not landed (coverage audit 2026-10-01, batch
c10_nst_rest).

Filter `posted='yes'`. The 57 `no` rows include alerts from as far back as 2019 ("Stewart Tunnel
closed", posted 2019-09). Loading all 80 would show expired closures as live. Gun-deer closures are
lines that close segments, so they `obstruct_trail` (decision 7). The NPS copy must be deduplicated
…

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`.../IAT_Trail_Conditions_Posted/FeatureServer/0`: 80 rows, last edit 2026-09-30. `posted`: yes 21, no"
        " 57, pending 2. Headings include Trail Closed 5, Trail closure 4, Logging Closure 3, Prescribed Burn "
        'Closure 2, Boardwalk Closed, Bridge Closed, and "Hunting Closure beginning 9/1 / 10/15 / 11/2 / '
        '11/22". Fields: `date_posted`, `date_updated`, `hyperlink`, `segment_name`. '
        "`.../IAT_Hunting_Closures/FeatureServer/0`: 52 polylines (`GunDeer` = Closed on 51, `OtherSeason` = "
        'Closed on 6), last edit 2026-09-21. The NPS Data API `alerts?parkCode=iatr` returns 16 (11 "Reroute in'
        ' Effect", 5 "Use …',
    ),
    where=(
        "https://dnrmaps.wi.gov/arcgis/rest/services",
        "https://iceagetrail.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
