"""Bay Area Ridge Trail Council: places, published, and not landed (coverage audit 2026-10-01, batch
c6_regional_3).

The trailhead "Directions" cells are hyperlinks, and the CSV export drops the targets (the cells
read just "Directions"). Getting coordinates needs the Sheets API or an HTML export.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Planning Navigator Google Sheet `1hAN0elCK83V_4A-gpNGxT7Tf3zPejXQ5y_DcLVWa8Wk`. CSV export: 84 section"
        ' rows, "Last Updated: 8/31/2026", with region, county, partner website, trailhead parking, parking '
        "fee, restrooms, permit required, shuttle and camping. The route layer also has `Park_Managers` and "
        "`Partner_Website` per segment.",
    ),
    where=("https://ridgetrail.org/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
