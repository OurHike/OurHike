"""National Mormon Trails Association: podcasts, published, and not landed (coverage audit 2026-10-01,
batch c11_nht).

Own `/videos/` reads "COMING SOON"; YouTube `@thenmta`

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=("`NPSAPI/multimedia/audio` mopi 10",),
    where=("https://mormontrails.org/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
