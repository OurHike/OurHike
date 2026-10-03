"""Oregon Natural Desert Association: photos, nothing published (coverage audit 2026-10-01, batch
c7_regional_4).

Not openly licensed.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=('Flickr `oregonnaturaldesert`: 17,722 photos, all 25 sampled `"license":0`.',),
    where=("https://onda.org/",),
)
