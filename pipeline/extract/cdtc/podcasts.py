"""Continental Divide Trail Coalition: podcasts, nothing published (coverage audit 2026-10-01, batch
b7_long_trails_states).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`cdtcoalition.org/wp-json/wp/v2/search?search=podcast` returned 8 posts, none of them a CDTC show. No "
        "podcast link on the homepage.",
        'Skeptic adds: Apple Podcasts search for "Continental Divide Trail Coalition" (8 shows) and '
        '"Continental Divide Trail" (1 show): none published by CDTC.',
    ),
    where=(
        "https://cdtcoalition.org/wp-json/wp/v2/search?search=podcast",
        "https://continentaldividetrail.org/",
    ),
)
