"""Nez Perce (Nee-Me-Poo) Trail Foundation: photos, nothing published (coverage audit 2026-10-01, batch
c11_nht).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=('`/photo-gallery/` exists (2014), footer reads "Copyright © 2014. All Rights Reserved." No open licence',),
    where=("https://nezpercetrail.net/",),
)
