"""Volunteers for Outdoor Colorado: places, nothing published (coverage audit 2026-10-01, batch
p03_persist).

none_stated.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "The DU `VOC_Projects` layers are the 64 Colorado counties tagged with VOC project counts, not places a"
        " hiker would look up. The My Maps layer is volunteer events (audit). Tried: 1–6 as for trail_lines.",
    ),
    where=("https://voc.org/",),
)
