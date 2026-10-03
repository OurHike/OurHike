"""Connecticut Forest & Park Association: trail lines, drawn from another folder's resource (coverage
audit 2026-10-01, batch c10_nst_rest).

The state copy is a near-copy of `Combined_BBHTs` (351 against 354). `BBHT_Public_Map_Trails` is
broader and updated two days ago. That is a #1709 pair.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Arrives via `ct-deep` as `ct_deep_blue_blazed` (351). The NET's CT half (Metacomet, Mattabesett, "
        "Menunkatuck) is 4 of those features. CFPA's own: `.../BBHT_Public_Map_Trails/FeatureServer/0`: 848 "
        'lines, 1,720.5 mi (`Dist_Mi`), last edit 2026-09-29, with `Blaze` (40+ values such as "CFPA Blue '
        'Rectangle" 131 and "Blue/Red Rectangle" 92), `NETWORK_NAME` and `trail_url`. '
        "`.../Combined_BBHTs_6_2025/FeatureServer/0`: 354, the interactive map's own layer.",
    ),
    where=(
        "https://services1.arcgis.com/FjPcSmEFuDYlIdKC/arcgis/rest/services",
        "https://ctwoodlands.org/",
    ),
    reason="drawn from ct_deep/'s resources, extracted once there (decision 34); checked names the layer this org's "
    "data arrives in",
)
