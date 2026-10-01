"""Central Iowa Trail Association: photos, nothing published (coverage audit 2026-10-01, batch
c5_regional_2).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=("The site links to a photographer (kkimages.us); no licence is stated.",),
    where=("https://kkimages.us",),
)
