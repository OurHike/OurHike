"""Standing Stone Trail Club: suggested hikes, published, and not landed (coverage audit 2026-10-01,
batch c8_regional_5).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'Per-map descriptions on `/pdf-maps` (e.g. "Jack\'s Narrows Close Up … a great day hike"). `/charters` '
        'events (e.g. "Lollipop MeetUp: Top of Jack\'s Mountain", 10/17). The SST Guide is "available for free '
        'upon request" and is not online.',
    ),
    where=(
        "https://mapservices.pasda.psu.edu/server/rest/services",
        "https://standingstonetrail.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
