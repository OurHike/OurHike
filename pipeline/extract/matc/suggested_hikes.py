"""Maine Appalachian Trail Club: suggested hikes, one trail's page, and not landed (decision 54 wave 5, section
K, 2026-10-04).

/grafton-loop-trail/ describes one trail, its two trailheads by driving directions; its only distance ('It is 7.3
miles north of the southern trailhead') is inside those directions. One route in paragraphs is not a list to read.

The note this replaces read, whole:

Maine Appalachian Trail Club: suggested hikes, published, and not landed (coverage audit 2026-10-01,
batch c1_at_clubs_north).

Thin: one route. The A.T. Guide to Maine is sold, not published.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): `https://www.matc.org/grafton-loop-trail/` (page): one route,
southern and northern trailheads with driving directions, the distance between them (7.3 mi), and the
first campsite 5 mi in.

Its `where`: https://www.matc.org/grafton-loop-trail/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "https://www.matc.org/grafton-loop-trail/ (HTTP 200, 112,422 bytes, 2026-10-04): 'Southern Trail Head' and 'Northern Trail Head' paragraphs of directions",
    ),
    where=("https://www.matc.org/grafton-loop-trail/",),
    reason="needs a per-site reader, not built in this pull request: one route whose facts are inside driving directions",
)
