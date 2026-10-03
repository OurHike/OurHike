"""Volunteers for Outdoor Colorado: points of interest, nothing published (coverage audit 2026-10-01,
batch p03_persist).

—

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "The same sources. The DU layers are county polygons, and the My Maps points are volunteer events. "
        "Tried: 1–6 as for trail_lines.",
    ),
    where=("https://voc.org/",),
)
