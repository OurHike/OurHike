"""Finger Lakes Trail Conference: warnings, published, and not landed (coverage audit 2026-10-01, batch
c4_regional_1).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "41 active notices flagged `tn_Hunting=1`. `…/Hunting_Bypasses_/FeatureServer/2` holds 69 bypass lines "
        "(lastEdit 2026-07-19). `/hunting-season-schedules/` lists NYS Southern Zone dates. Waypoints include "
        "`Advisory` (7) and `HuntingClosures` (76).",
    ),
    where=("https://fingerlakestrail.org/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
