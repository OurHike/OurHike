"""Catamount Trail Association: podcasts, nothing published (coverage audit 2026-10-01, batch
c4_regional_1).

Skeptic re-checked 2026-10-01: searches for "audio" and "episode" turn up only the "Backcountry Show
& Tell Video Series", which is video. Stands.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=('WP search for "podcast" returned 1 hit, a profile post.',),
    where=("https://catamounttrail.org/",),
)
