"""NYC Parks: suggested hikes, refused by nycgovparks.org's robots.txt (decision 54 wave 3, section C,
2026-10-04).

Both machine-readable sources sit under nycgovparks.org and end in `json`: DPR_Hiking_001.json (62
named trails) and /xml/events_300_rss.json (dated events). The host's robots.txt disallows them for
every agent: `Disallow: /*json` (decision 53's inventory, batch 1, 2026-10-03). A refusal is a note,
never a puzzle (the dlt skill).

The note this replaces read, whole:

NYC Parks: suggested hikes, published, and not landed (coverage audit 2026-10-01, batch
b5_nyc_nj_ct_ma_pa).

The hiking feed holds descriptions, not routes. The guided hikes are dated events, so a mart row
needs an expiry.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "nycgovparks.org's robots.txt, as decision 53's inventory quoted it (batch 1, 2026-10-03): `Disallow: /*json` under `User-agent: *`; nothing on the host was asked today.",
        '(the coverage audit, 2026-10-01) `DPR_Hiking_001.json`: 62 named trails in 56 parks, with `Length`, `Difficulty` (Various 28, Easy 18, Moderate 7…) and `Other_Details` prose. It has no coordinates, only `Prop_ID`. Regenerated 2026-09-30. `https://www.nycgovparks.org/xml/events_300_rss.json`: 955 events in the next 14 days, of which 18 are in category "Hiking" and 39 are "Urban Park Rangers" events. Each has a meeting-point `coordinates` value, `startdate` and `parkids`.',
    ),
    where=(
        "https://www.nycgovparks.org/robots.txt",
        "https://www.nycgovparks.org/xml/events_300_rss.json",
    ),
    terms="robots.txt: `Disallow: /*json` (www.nycgovparks.org, for every agent)",
    reason="refused: the host's robots.txt disallows every URL ending in json for every agent",
)
