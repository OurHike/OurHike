"""The Cohos Trail Association: places, published as a list with no coordinate, and not landed (decision 54, wave
5, read 2026-10-04). The businesses page lists businesses and campgrounds south to north with no fix, and a
business is never looked up from its name.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "www.cohostrail.org/robots.txt (WooCommerce's paths and /wp-admin/ disallowed), then "
        "/businesses-along-the-trail/, read 2026-10-04 under lib/user_agent.py's agent: 200, 84,780 bytes, no "
        "coordinate in the page.",
        "the coverage audit (2026-10-01, batch c4_regional_1): 21 businesses and campgrounds; /shuttle-options/.",
    ),
    where=("https://www.cohostrail.org/businesses-along-the-trail/",),
    reason="needs a per-site reader, not built in this pull request: businesses and campgrounds named with no coordinate",
)
