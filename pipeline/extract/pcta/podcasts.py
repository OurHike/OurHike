"""Pacific Crest Trail Association: podcasts, nothing published (coverage audit 2026-10-01, batch
b7_long_trails_states).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'A web search for "Pacific Crest Trail Association podcast" returned only third-party shows (a named '
        'individual "Pacific Crest Trail, Then and Now"). `pcta.org/feed/` (HTTP 200): its 10 latest items are '
        "articles.",
        "Skeptic adds: the site's own search, `pcta.org/feed/?s=podcast` (HTTP 200), returned 10 posts, each "
        "mentioning someone else's show (Backpacker Radio, a BLM podcast, Cascade Hiker, Sounds of the Trail, "
        'KHUM). Apple Podcasts directory search (`itunes.apple.com/search?media=podcast`) for "Pacific Crest '
        'Trail Association" and for "Pacific Crest Trail" returned 3 and 8 shows, none …',
    ),
    where=(
        "https://pcta.org/feed/",
        "https://pcta.org/feed/?s=podcast",
        "https://itunes.apple.com/search?media=podcast",
        "https://pcta.org/",
    ),
)
