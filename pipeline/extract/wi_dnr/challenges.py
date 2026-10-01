"""Wisconsin DNR Open Data: challenges, published, and not landed (coverage audit 2026-10-01, batch
b7_long_trails_states).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Format page: the Wisconsin Explorer Program `dnr.wisconsin.gov/topic/parks/learn/explorer` (HTTP 200; "
        'a children\'s patch programme, per search). The 22-item "Explore Challenge" belongs to the Friends of '
        "Wisconsin State Parks, not WDNR.",
    ),
    where=("https://dnr.wisconsin.gov/topic/parks/learn/explorer",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
