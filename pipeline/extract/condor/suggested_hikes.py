"""Condor Trail Association: suggested hikes, nothing published (coverage audit 2026-10-01, batch
c7_regional_4).

Broken file.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        '`/maps-trail-descriptions/` names only the termini. Its "Condor Trail Mileage.xlsx" link '
        "(`http://www.condortrail.com/Condor%20Trail%20Mileage.xlsx`) returns a saved Wayback Machine HTML page"
        " (10,890 B), not a spreadsheet.",
    ),
    where=("https://condortrail.com/",),
)
