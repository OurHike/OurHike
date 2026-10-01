"""The Cohos Trail Association: trail lines, published, and not landed (coverage audit 2026-10-01,
batch c4_regional_1).

Paid only. The southern WMNF stretch is partly LOADED via `usfs_trails`: Davis Path is 19 segments
and Kilkenny Ridge 2. Those trails being on the route is R, from the CTA's "begins on the Davis
Path". Not in GRANIT: 0 matches on `TRAILSYSTE`/`TRAILNAME` today. On ArcGIS, only `andyf0722`, a …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        '`https://www.cohostrail.org/product-category/maps/`: "Cohos Trail Map (2023 Edition) $16.95" and '
        '"Digital Map (Avenza Maps) 2023 $16.99".',
    ),
    where=("https://www.cohostrail.org/product-category/maps/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
