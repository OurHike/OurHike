"""The Anza Trail Foundation: photos, published, and not landed (coverage audit 2026-10-01, batch
c11_nht).

The site's own photos are rights-retained

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=("`NPSAPI/multimedia/galleries` juba 10",),
    where=("https://anzatrailfoundation.com/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
