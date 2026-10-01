"""Colorado Mountain Club: warnings, nothing published (coverage audit 2026-10-01, batch p06_persist).

Whether CAIC offers a reusable feed is UNKNOWN. It would go in `_shared/caic/` if anyone pursues it.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "The search index has `cmc.org/conservation/snow-rangers` and two blog posts. They describe an "
        'in-person patrol programme run December to April in support of USFS: "four CMC Snow Rangers completed '
        '45 patrol days and more than 840 hours … across the Uncompahgre and Grand Mesa National Forests". That'
        " is not a notice channel. For avalanche warnings, avalanche.org's public map layer "
        "(`api.avalanche.org/v2/public/products/map-layer`) holds 83 zones from 28 centres, and 0 are Colorado:"
        " CAIC is not in it. CAIC's own endpoint was not identifiable from its home page. Tried: 2, 4 (USFS; "
        "CAIC), 6 and 7 …",
    ),
    where=(
        "https://cmc.org/conservation/snow-rangers",
        "https://avalanche.org",
        "https://api.avalanche.org/v2/public/products/map-layer",
    ),
)
