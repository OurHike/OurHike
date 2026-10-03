"""Randolph Mountain Club: trail lines, drawn from another folder's resource (coverage audit
2026-10-01, batch c1_at_clubs_north).

RMC's own ~98 non-A.T. miles are not loaded from any RMC source. Trailforks is proprietary
third-party data. The #1709 dual-source flag is stale (see above).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'Club polygon "Randolph Mountain Club" (the A.T. part only). RMC\'s own: ArcGIS `RMC_cartographer` items'
        " `48365ef2…` (tile Map Service), `4fcc028b…` (app), `1281472c…` (web map), `7df9a5b2…` (layer). All "
        'return 403 SB_0006 "Subscription is canceled", and the tile service returns 499 Token Required. The '
        "site's interactive map is a Trailforks widget "
        "(`https://www.trailforks.com/region/randolph-mountain-club-trail-network/`).",
    ),
    where=(
        "https://www.trailforks.com/region/randolph-mountain-club-trail-network/",
        "https://randolphmountainclub.org/",
    ),
    reason="drawn from atc/'s resources, extracted once there (decision 34); checked names the layer this org's data arrives in",
)
