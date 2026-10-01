"""Green Mountain Club: challenges, published, and not landed (coverage audit 2026-10-01, batch
c1_at_clubs_north).

Side-to-Side is a defined trail list, which fits #1780's shape.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Long Trail End-to-Ender Certification (`/hike/thru-hiking/long-trail-end-to-ender-certification/`): "
        '"More than 7,000" certified, certificate and patch. Side-to-Sider: all 88 side trails (166 mi), with '
        "tracker PDF `/wp-content/uploads/2026/04/Long-Trail-Side-to-Side-Tracker.pdf`.",
    ),
    where=("https://greenmountainclub.org/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
