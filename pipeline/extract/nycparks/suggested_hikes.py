"""NYC Parks: suggested hikes, published, and not landed (coverage audit 2026-10-01, batch
b5_nyc_nj_ct_ma_pa).

The hiking feed holds descriptions, not routes. The guided hikes are dated events, so a mart row
needs an expiry.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`DPR_Hiking_001.json`: 62 named trails in 56 parks, with `Length`, `Difficulty` (Various 28, Easy 18, "
        "Moderate 7…) and `Other_Details` prose. It has no coordinates, only `Prop_ID`. Regenerated 2026-09-30."
        " `https://www.nycgovparks.org/xml/events_300_rss.json`: 955 events in the next 14 days, of which 18 "
        'are in category "Hiking" and 39 are "Urban Park Rangers" events. Each has a meeting-point '
        "`coordinates` value, `startdate` and `parkids`.",
    ),
    where=("https://www.nycgovparks.org/xml/events_300_rss.json",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
