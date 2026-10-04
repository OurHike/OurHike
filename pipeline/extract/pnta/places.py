"""Pacific Northwest Trail Association: places, published as a page with no coordinate, and not landed (decision
54, wave 5, read 2026-10-04). The trail towns and resupply page describes each town in prose, with no fix; the
overview map's 'Trail Town/ Resupply Point' symbols are the same towns, drawn (pnta/points_of_interest.py). A
town is never looked up from its name.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "pnt.org/robots.txt (Yoast's, `Disallow:` empty), then "
        "/pnta/know-before-you-go/plan-your-trip/trail-towns-resupply/, read 2026-10-04 under lib/user_agent.py's "
        "agent: 200, 211,065 bytes, no coordinate in the page.",
        "the coverage audit (2026-10-01, batch c10_nst_rest): /trail-towns-resupply/, /backcountry-permits/, /permits-fees/.",
    ),
    where=("https://pnt.org/pnta/know-before-you-go/plan-your-trip/trail-towns-resupply/",),
    reason="needs a per-site reader, not built in this pull request: trail towns in prose with no coordinate",
)
