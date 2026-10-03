"""Old Dominion Appalachian Trail Club: points of interest, published, and not landed (coverage audit
2026-10-01, batch c2_at_clubs_mid).

Do not load as is. A water report last updated in 2018 is worse than none. The reliability column is
the only part that ages slowly, and even that is Unvalidated. Skeptic new find: `/page-924714`
("Trail Maintenance Overview", HTML page) carries "ODATC Section Descriptions", about 45 landmarks …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`/ODATC-Water-Board-Updates` → XLSX "
        "`https://odatc.org/resources/Documents/ODATC%20Water%20Board%202018-4.xlsx` (10 KB, Last-Modified "
        '2018-04-22): about 8 water sources by miles from Rockfish Gap, each with reliability ("flows all '
        'year", "unreliable", "May–Oct") and a last-reported date. Shelters LOADED via atc (Paul C. Wolfe, '
        "capacity 10)",
    ),
    where=(
        "https://odatc.org/resources/Documents/ODATC%20Water%20Board%202018-4.xlsx",
        "https://odatc.net/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
