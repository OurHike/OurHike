"""Connecticut Forest & Park Association: points of interest, published, and not landed (coverage audit
2026-10-01, batch c10_nst_rest).

No water layer. The 17 A.T. sites overlap ATC's shelters and campsites, so they need deduplication
after extract-load. Skeptic spot-check: `BBHT_Public_Points_(New)/1` = 32. The layer's own
`editingInfo.lastEditDate` reads 2026-09-11, not 2026-09-25. The later date is probably the
service's or the …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`.../BBHT_Public_Points_(New)/FeatureServer/1` Overnight Site Points: 32: 16 shelters and 16 "
        "campsites. 17 are flagged `AT`, 4 `NET`, with `RESERVATION_REQ` and `MAINT_ORG`. Last edit 2026-09-25."
        " Layer `/0` Parking: 365, all `STATUS` open and `SHOW_PUBLIC` yes. `CTTrailsMapData/0–1` is the older "
        "copy (373 parking, 16 overnight).",
    ),
    where=(
        "https://services1.arcgis.com/FjPcSmEFuDYlIdKC/arcgis/rest/services",
        "https://ctwoodlands.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
