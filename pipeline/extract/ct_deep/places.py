"""Connecticut DEEP: places, published, and not landed (coverage audit 2026-10-01, batch
b5_nyc_nj_ct_ma_pa).

Skeptic, 2026-10-01: also
`https://services1.arcgis.com/FjPcSmEFuDYlIdKC/arcgis/rest/services/Greenways/FeatureServer/0`
"Official Designated Connecticut Greenways" (owner `deepgis`): 120 polylines with `NAME`, `OD_YEAR`
and `GREENWAY_DESCRIPTION`, edited 2026-02-19, `licenseInfo: CC0`. These are …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`Connecticut_DEEP_Property/0`: 491 polygons (state parks, forests, WMAs), CC0, edited 2026-08-19. "
        "`data.ct.gov` federates the same items (`3ikr-b6ij` etc.) and holds no separate copy.",
    ),
    where=(
        "https://services1.arcgis.com/FjPcSmEFuDYlIdKC/arcgis/rest/services/Greenways/FeatureServer/0",
        "https://data.ct.gov",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
