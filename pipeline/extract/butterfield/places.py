"""Butterfield Overland Trail Association: places, published, and not landed (coverage audit
2026-10-01, batch c11_nht).

No coordinates

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'Own: `/stage-stations/` (by division, prose locations such as "12 miles south of San Francisco", '
        "HTML). `NPSAPI/places` buov ≥3",
    ),
    where=("https://butterfieldtrail.org/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
