"""Tahoe Rim Trail Association: podcasts, nothing published (coverage audit 2026-10-01, batch
b7_long_trails_states).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`wp-json/wp/v2/search?search=podcast` returned 0. `/trail-talks/` is an in-person event series.",
        'Skeptic adds: Apple Podcasts search "Tahoe Rim Trail": 8 shows, none TRTA\'s. A web search finds TRTA '
        "staff as guests on Bush & Banter (2025-07-09) and The Trail Show #115. Those are other people's shows:"
        " candidates for the editorial `reference/podcast_episodes.json`, not a TRTA feed. `tahoerimtrail.org` "
        "now answers 403 (Cloudflare) to curl from this sandbox, so the `wp-json` search cannot be re-run here "
        "today.",
    ),
    where=(
        "https://tahoerimtrail.org",
        "https://tahoerimtrail.org/",
    ),
)
