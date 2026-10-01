"""Sierra Buttes Trail Stewardship: trail lines, published, and not landed (coverage audit 2026-10-01,
batch c6_regional_3).

Most of these are Forest Service system trails, so `usfs_trails` likely already holds the geometry
(Reasoned). #1711 — Ship only hiking trails: remove NH GRANIT, and drop USFS motorized trails
nationwide removed USFS motorized trails, so the 413 motorized segments are probably exactly what is
…

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'Own ArcGIS: "SBTS Maintained", '
        "`https://services6.arcgis.com/t5asxkRF7xoBwgqv/arcgis/rest/services/SBTS_Maintained/FeatureServer/6` "
        "(a personal ArcGIS account). 565 polylines, ≈834 mi: Motorized 413 segments / 482.2 mi, Non-Motorized "
        "143 / 293.7 mi, untyped 9 / 58.5 mi. By forest: Plumas NF 540, Tahoe NF 18. Data last edited "
        "2022-01-17. Files: `https://sierratrails.org/s/Connected-Communties-Route-Alternative-B-gpx.zip` "
        '(`HEAD`: 1,636,968 bytes; the page says "30MB") and `…-kmz.zip` (1,306,465 bytes; the page says '
        '"3.2MB").',
    ),
    where=(
        "https://services6.arcgis.com/t5asxkRF7xoBwgqv/arcgis/rest/services/SBTS_Maintained/FeatureServer/6",
        "https://sierratrails.org/s/Connected-Communties-Route-Alternative-B-gpx.zip",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
