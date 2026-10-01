"""Black Hills Trails: closures, published, and not landed (coverage audit 2026-10-01, batch
p10_persist).

Pages and RSS, not GIS, so decision 21's presumption does not apply. Both are federal works: public
domain under `usfs_licence` (17 U.S.C. 105) and the same basis for BLM. Folders: `usfs/`, `blm/`.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`https://www.fs.usda.gov/r02/blackhills/alerts` (HTML) holds 23 alerts. Each is typed critical, "
        'fire-restriction, caution or information, with an "Alert Start Date" and usually a Forest Order '
        'number. Examples: "Veteran\'s Point Area and Trail Closure" (Order BKF-196-2026, 2026-08-16); "Pactola '
        'Loop B and Osprey Trail Closure" (2026-08-06). There is no feed: `/alerts/rss.xml`, `/alerts/feed` and'
        " `/rss.xml` answer 404, and `?_format=json` answers 406. robots.txt allows `/alerts`. BLM "
        "Montana-Dakotas press releases `https://www.blm.gov/press-release/montana-dakotas/rss` (RSS) hold 50 "
        "items …",
    ),
    where=(
        "https://www.fs.usda.gov/r02/blackhills/alerts",
        "https://www.blm.gov/press-release/montana-dakotas/rss",
        "https://blackhillstrails.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
