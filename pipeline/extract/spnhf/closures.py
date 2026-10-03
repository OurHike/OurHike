"""Society for the Protection of NH Forests: closures, published, and not landed (coverage audit
2026-10-01, batch c4_regional_1).

Terms-gated. `c12_umbrella_route_aggregator.md` measured OuterSpatial's terms as "permits you to use
the Website for your personal, non-commercial use". So this is a maintainer decision (ask the Forest
Society, or OuterSpatial), not a fetcher. Low volume and stale-looking. The app's push …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`https://www.outerspatial.com/organizations/society-for-the-protection-of-new-hampshire-forests` is a "
        'public HTML page with a "Bulletin Board" of ~35 items. They include closure and opening notices ("The '
        'Rocks\' Trails & Fields Closed to Visitors for Carriage Barn Construction", "Trails are OPEN at The '
        'Rocks!"). The timestamps embedded near those items run 2020–2024, and the newest item reads "Cheers to'
        ' getting outside in 2025!". forestsociety.org itself carries free-text status banners on property '
        'pages, e.g. `/property/mount-major-reservation`: "The parking lot at Mt. Major is OPEN and the …',
    ),
    where=(
        "https://www.outerspatial.com/organizations/society-for-the-protection-of-new-hampshire-forests",
        "https://forestsociety.org",
        "https://forestsociety.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
