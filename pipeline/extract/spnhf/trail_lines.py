"""Society for the Protection of NH Forests: trail lines, published, and not landed (coverage audit
2026-10-01, batch c4_regional_1).

The layer is a 2020 GRANIT-derived copy. GRANIT's `MAINTAINED` = "SOCIETY FOR THE PROTECTION OF NH
FORESTS" on 200 segments today, but GRANIT is retired (#1711).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'ArcGIS a personal ArcGIS account, "ES Public Access Map 4272020_WFL1", '
        "`https://services8.arcgis.com/3SFpHP4jeQ4r5jD5/arcgis/rest/services/ES_Public_Access_Map_4272020_WFL1/FeatureServer/1`"
        ' ("NH Public Trails"): 567 polylines, lastEdit 2020-04-30. Per-property trail-map PDFs, e.g. '
        "`/document/map-mount-major-trails.pdf`. OuterSpatial app.",
    ),
    where=(
        "https://services8.arcgis.com/3SFpHP4jeQ4r5jD5/arcgis/rest/services/ES_Public_Access_Map_4272020_WFL1/FeatureServer/1",
        "https://forestsociety.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
