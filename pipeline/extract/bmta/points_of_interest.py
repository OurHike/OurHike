"""Benton MacKaye Trail Association: points of interest, published, and not landed (coverage audit
2026-10-01, batch c8_regional_5).

PDF table with machine-parseable coordinates. The 2020 date is stale-risk for parking.
"Predominantly a tent/tarp/hammock trail."

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        '"Access Points/Trailheads" PDF, '
        "`https://bmta.org/wp-content/uploads/2020/05/Access-PointsTrailheads.pdf`. ~~(curl gets 403)~~",
        "Skeptic, read 2026-10-01: 200, 530,133 B, 4 pages, created 2020-05-24. It is a table of 48 access "
        "points, each with BMT mile, location, trailhead name, Hiking Project section, road name and "
        "latitude/longitude in degrees and decimal minutes (`N34° 38.116 W84° 10.452`). 47 rows carry "
        'coordinates; "Weaver Creek Road" (mile 46) has none. The Thru-Hikers\' Guide (page) names the one BMT '
        'shelter, "on the Sisson property at mile 50.3", and says water is "generally, not a …',
    ),
    where=("https://bmta.org/wp-content/uploads/2020/05/Access-PointsTrailheads.pdf",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
