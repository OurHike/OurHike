"""Wisconsin DNR Open Data: podcasts, published, and not landed (coverage audit 2026-10-01, batch
b7_long_trails_states).

Dormant for five years. Load only if the podcasts mart accepts archives. SilviCast is live, but its
audience is foresters, so it is a weak fit.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        '"Wild Wisconsin – Off the Record": RSS `https://feeds.transistor.fm/wild-wisconsin-off-the-record`, 59'
        " episodes, latest release 2021-06-16 (iTunes id 1392683302).",
        'Skeptic adds (Measured, Apple Podcasts search "Wisconsin Department of Natural Resources"): SilviCast,'
        " by the Wisconsin Forestry Center and the Wisconsin Department of Natural Resources: RSS "
        "`https://rss.buzzsprout.com/1135730.rss`, 70 episodes, latest 2026-08-03 (id 1518316928). It is "
        "active, co-produced, and about forestry practice rather than hiking.",
    ),
    where=(
        "https://feeds.transistor.fm/wild-wisconsin-off-the-record",
        "https://rss.buzzsprout.com/1135730.rss",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
