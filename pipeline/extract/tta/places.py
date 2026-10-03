"""Tennessee Trails Association: places, published, and not landed (coverage audit 2026-10-01, batch
c5_regional_2).

Machine-readable, but these are event meeting spots: "Meeting Spot" appears three times at one
coordinate. Terms forbid republishing.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "WordPress REST `https://tennesseetrails.org/wp-json/tribe/events/v1/venues` (JSON, `total` = 153 "
        'venues). Some carry `geo_lat`/`geo_lng`, e.g. "Beaman Park Creekside Trailhead" at 36.273621, '
        "-86.904652.",
    ),
    where=(
        "https://tennesseetrails.org/wp-json/tribe/events/v1/venues",
        "https://tennesseetrails.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
