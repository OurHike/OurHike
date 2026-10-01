"""Appalachian Mountain Club (A.T. sections): podcasts, published, and not landed (coverage audit
2026-10-01, batch c1_at_clubs_north).

Dormant feed.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Unlikely Stories Podcast, announced at "
        "`/resources/amc-outdoors/news/amc-presents-unlikely-stories-podcast/`. RSS "
        "`https://feeds.simplecast.com/UC2QUufg`: 11 episodes, last 2021-10-27 (iTunes Search API).",
    ),
    where=(
        "https://feeds.simplecast.com/UC2QUufg",
        "https://outdoors.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
