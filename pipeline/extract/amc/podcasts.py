"""Appalachian Mountain Club: podcasts, published, and not landed (coverage audit 2026-10-01, batch
c10_nst_rest).

Dormant and of low hiker value. If it is loaded, it goes in `_shared/` podcasts (decision 12).
Skeptic spot-check: the feed has 11 `<item>`s, the newest dated 2021-10-27. The channel
`<copyright>` is "Appalachian Mountain Club", and the iTunes author is a named individual (host), so
it is AMC's own …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Unlikely Stories Podcast, RSS `https://feeds.simplecast.com/UC2QUufg`: 11 episodes, last 2021-10-27 (iTunes lookup).",
    ),
    where=("https://feeds.simplecast.com/UC2QUufg",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
