"""Friends of the Mountains-to-Sea Trail: suggested hikes, published, and not landed (coverage audit
2026-10-01, batch c7_regional_4).

Probably PDF. Not opened, because of the captcha.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=('Segment pages, each with "a downloadable Trail Guide" (search snippet), and `/the-trail/trail-guides/`.',),
    where=("https://mountainstoseatrail.org/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
