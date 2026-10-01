"""Mazamas: challenges, published, and not landed (coverage audit 2026-10-01, batch c6_regional_3).

Each counts only summits made "on official Mazama climbs", so this is a club-member programme for
mountaineering summits. It fits #1780 only loosely.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`/awards/` names three peak awards: Guardian Peaks (3 peaks, about 2,000 earned), Seven Oregon Cascade"
        " Peaks (7, about 700), and Sixteen Major Northwest Peaks (16, a plaque, about 500). HTML.",
    ),
    where=("https://mazamas.org/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
