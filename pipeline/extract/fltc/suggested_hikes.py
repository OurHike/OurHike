"""Finger Lakes Trail Conference: suggested hikes, published as passport booklets and a page of special places,
and not landed (decision 54 wave 5, section K, 2026-10-04).

The Passport Hikes are three booklets of 12 hikes (the coverage audit) and the 21 PassportHikes waypoints are an
ArcGIS layer's, the lead's; /plan-hikes-finger-lakes-trail/special-places/ describes places in prose; the
Cross-County Hike Series is events. fingerlakestrail.org's robots.txt disallows /FLTC/ and /REF/.

The note this replaces read, whole:

Finger Lakes Trail Conference: suggested hikes, published, and not landed (coverage audit 2026-10-01,
batch c4_regional_1).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): Passport Hikes: 3 booklets × 12 hikes, 21 `PassportHikes`
waypoints. `/plan-hikes-finger-lakes-trail/special-places/`. The Cross-County Hike Series (events).

Its `where`: https://fingerlakestrail.org/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "https://fingerlakestrail.org/plan-hikes-finger-lakes-trail/special-places/ (HTTP 200, 243,667 bytes, 2026-10-04T15:38:10Z): places in prose",
    ),
    where=("https://fingerlakestrail.org/plan-hikes-finger-lakes-trail/special-places/",),
    reason="needs a per-site reader, not built in this pull request: places in prose, the passport hikes in booklets",
)
