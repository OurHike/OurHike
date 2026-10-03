"""Florida Trail Association: photos, nothing published (coverage audit 2026-10-01, batch
c10_nst_rest).

Using these needs permission. That is a maintainer question, not a load.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=("Media room → `https://ft.smugmug.com/`. No licence is stated. ArcGIS images are logos.",),
    where=("https://ft.smugmug.com/",),
)
