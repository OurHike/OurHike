"""Appalachian Mountain Club (A.T. sections): podcasts, drawn from amc/podcasts.py's
`amc_unlikely_stories_podcast` (decision 54 wave 3, section C, 2026-10-04).

The Unlikely Stories Podcast is AMC's own show, one feed, extracted once in amc/ (decision 34); this
folder, the same organisation's A.T. sections, writes no second resource for it.

The note this replaces read, whole:

Appalachian Mountain Club (A.T. sections): podcasts, published, and not landed (coverage audit
2026-10-01, batch c1_at_clubs_north).

Dormant feed.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "Unlikely Stories Podcast (section C, 2026-10-04): landed by amc/podcasts.py as amc_unlikely_stories_podcast, 11 episodes, 2021-08-24 to 2021-10-27.",
        "(the coverage audit, 2026-10-01) Unlikely Stories Podcast, announced at `/resources/amc-outdoors/news/amc-presents-unlikely-stories-podcast/`. RSS `https://feeds.simplecast.com/UC2QUufg`: 11 episodes, last 2021-10-27 (iTunes Search API).",
    ),
    where=(
        "https://feeds.simplecast.com/UC2QUufg",
        "https://outdoors.org/",
    ),
    reason="drawn from amc/'s resource, extracted once there (decision 34); checked names the feed this org's show arrives in",
)
