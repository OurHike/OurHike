"""Utah UGRC — SGID Trails and Pathways: closures, published, and not landed (coverage audit
2026-10-01, batch b7_long_trails_states).

Map it in staging. No separate feed exists.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=("An attribute in the loaded layer: `Status = CLOSED` on 122 segments. Nothing reads it (section B).",),
    where=("https://services1.arcgis.com/99lidPhWCzftIe9K/ArcGIS/rest/services",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
