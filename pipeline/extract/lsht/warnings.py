"""Lone Star Hiking Trail Club: warnings, published, and not landed (coverage audit 2026-10-01, batch
c8_regional_5).

ClubExpress news, page only, no feed found. The hunting rule has explicit dates, so it fits the
warnings mart. Skeptic, new and stale: web map "LSHT Survey2024"
(`661f31eba56644f09d5908a6b21ed4b8`) layers a "Down Trees Labeled" WMS
(`wms.qgiscloud.com/richwinters/trees`) and a public GeoJSON …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'News (`page_id=3`): "DESIGNATED CAMPING IN EFFECT DURING HUNTING SEASON — Designated camping policy in'
        ' effect September 26, 2026 to January 24, 2027." The Burn Maps page (`module_id=677565`) links the R8 '
        "burn layer (Texas NFs, 386 blocks).",
    ),
    where=("https://wms.qgiscloud.com/richwinters/trees",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
