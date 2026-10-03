"""USGS — The National Map: podcasts, published, and not landed (coverage audit 2026-10-01, batch
c9_federal_state_rest).

Science programming, not trail audio.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        '"Outstanding in the Field" RSS, `https://www.usgs.gov/podcasts/audio/141799/feed.xml`; CoreCast (former series).',
        'Skeptic: the feed answers HTTP 200 `application/rss+xml` with title "Outstanding in the Field" when '
        "sent a browser user agent. The 403 was a user-agent filter, not a missing feed.",
    ),
    where=("https://www.usgs.gov/podcasts/audio/141799/feed.xml",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
