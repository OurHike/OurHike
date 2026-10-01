"""Colorado Parks & Wildlife — COTREX: podcasts, published, and not landed (coverage audit 2026-10-01,
batch b7_long_trails_states).

Active.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        '"Colorado Outdoors – the Podcast for Colorado Parks and Wildlife": RSS '
        "`https://rss.art19.com/colorado-outdoors`, 54 episodes, latest 2026-10-01 (iTunes lookup, id "
        "1537137938). Page: `cpw.state.co.us/CPW-podcast`.",
    ),
    where=(
        "https://rss.art19.com/colorado-outdoors",
        "https://cpw.state.co.us/CPW-podcast",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
