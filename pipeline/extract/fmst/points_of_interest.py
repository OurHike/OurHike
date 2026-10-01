"""Friends of the Mountains-to-Sea Trail: points of interest, published, and not landed (coverage audit
2026-10-01, batch c7_regional_4).

Machine-readable. The sheet's own words are: "can be used or adapted as you like … use the
spreadsheet at your own risk". That is a stated permission, worth recording in `licence_basis`.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        '"Primary Trailheads" Google Sheet, exported as CSV: '
        "`https://docs.google.com/spreadsheets/d/1RQYQ9d0uYc4tiw3kDoANY7ZgQuXDSuj4AyW44Kv7-xQ/export?format=csv`."
        ' 264 trailhead rows with lat/lon, EB/WB mile and notes. The sheet reads "Current as of: 8/12/2026".',
    ),
    where=("https://docs.google.com/spreadsheets/d/1RQYQ9d0uYc4tiw3kDoANY7ZgQuXDSuj4AyW44Kv7-xQ/export?format=csv",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
