"""Wisconsin DNR: challenges, a children's explorer programme, and not landed (decision 54 wave 5, section K,
2026-10-04).

The Wisconsin Explorer Program is a children's patch programme of activity booklets, not a list of places; the
22-item 'Explore Challenge' is the Friends of Wisconsin State Parks', not the department's (the coverage audit). No
request sent today.

The note this replaces read, whole:

Wisconsin DNR Open Data: challenges, published, and not landed (coverage audit 2026-10-01, batch
b7_long_trails_states).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): Format page: the Wisconsin Explorer Program
`dnr.wisconsin.gov/topic/parks/learn/explorer` (HTTP 200; a children's patch programme, per search). The
22-item "Explore Challenge" belongs to the Friends of Wisconsin State Parks, not WDNR.

Its `where`: https://dnr.wisconsin.gov/topic/parks/learn/explorer

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "(the coverage audit, 2026-10-01) dnr.wisconsin.gov/topic/parks/learn/explorer",
        "no request sent today: the coverage audit's reading, 2026-10-01",
    ),
    where=("https://dnr.wisconsin.gov/topic/parks/learn/explorer",),
    reason="not this type: a children's activity-booklet programme, no list of places",
)
