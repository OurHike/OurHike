"""The Cohos Trail Association: points of interest, published with no coordinate, and not landed (decision 54,
wave 5, read live 2026-10-04).

The association's places-to-stay page names its shelters, cabins and huts south to north, with no coordinate.
The Baldhead Shelter was removed in 2025 (/trail-changes-and-updates/, the coverage audit 2026-10-01), so a
shelter list read from an older source would send a hiker to a shelter that is gone. A point is never looked up
from a name; needs a per-site reader, not built in this pull request, and a fix for each that a person reviews.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "robots.txt (WooCommerce's paths, /wp-admin/ and /imunify-bot-check disallowed, no Crawl-delay), then "
        "/places-to-stay/, read 2026-10-04 under lib/user_agent.py's agent: 200, 87,963 bytes; no coordinate, "
        "decimal or DDM, in the page.",
        "the coverage audit (2026-10-01, batch c4_regional_1): `/places-to-stay/` names 8 shelters, cabins and "
        "huts, south to north; also `/supply-chache/`.",
    ),
    where=("https://www.cohostrail.org/places-to-stay/",),
    reason="needs a per-site reader, not built in this pull request: the shelters are named with no coordinate",
)
