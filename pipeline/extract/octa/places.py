"""Oregon-California Trails Association: places, published, and not landed (coverage audit 2026-10-01,
batch c11_nht).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'Own: `https://octa-trails.org/trail-sites/` ("Trail Sites - OCTA", search index; page, contents '
        "unread). Upstream: `NPSAPI/places` oreg ≥57, cali ≥73",
    ),
    where=("https://octa-trails.org/trail-sites/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
