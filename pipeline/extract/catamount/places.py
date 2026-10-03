"""Catamount Trail Association: places, published, and not landed (coverage audit 2026-10-01, batch
c4_regional_1).

Machine-readable CSV. The `trail_zone` WP type exists, but its REST endpoint returns `x-wp-total:
0`.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`…/data/CTA_POI_MASTER_WEBMAP.csv`: 77 lodging/food/Nordic/alpine businesses with lat/lon (2017). "
        "`…/CTA_BACKCOUNTRY_MASTER_WEBMAP.csv`: 6 backcountry zones. Plus the `/bc-zones/` pages.",
    ),
    where=("https://catamounttrail.org/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
