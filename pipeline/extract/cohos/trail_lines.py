"""The Cohos Trail Association: trail lines, sold rather than published, and not landed (decision 54, wave 5,
read live 2026-10-04).

The association sells its map, in print and through Avenza, and publishes no line of its own. The southern
White Mountain National Forest stretch is partly drawn already through `usfs_trails` (Davis Path, 19 segments,
and Kilkenny Ridge, 2), the trail's route on them being the association's "begins on the Davis Path" (Reasoned,
the coverage audit 2026-10-01); NH GRANIT holds no Cohos line (0 matches on `TRAILSYSTE` and `TRAILNAME`).
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "robots.txt (WooCommerce's paths and /wp-admin/ disallowed, no Crawl-delay), then /product-category/maps/, "
        "read 2026-10-04 under lib/user_agent.py's agent: 200, 87,802 bytes, the store's map products; no GPX, KML "
        "or GeoJSON is linked.",
        "the coverage audit (2026-10-01, batch c4_regional_1): 'Cohos Trail Map (2023 Edition) $16.95' and "
        "'Digital Map (Avenza Maps) 2023 $16.99'; not in GRANIT; on ArcGIS only one person's account, a lead only.",
    ),
    where=("https://www.cohostrail.org/product-category/maps/",),
    reason="sold, not published: the trail's map is a product, and no line of the association's own is public",
)
