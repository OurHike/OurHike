"""Maah Daah Hey Trail Association: trail lines, drawn from another folder's resource (coverage audit
2026-10-01, batch c8_regional_5).

The FAQ says the GPX may differ from the 2018 printed map because of reroutes.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Via `usfs` → `usfs_trails`: `MAAH DAAH HEY` 011807, 21 / 110.63 mi, and 011808, 10 / 34.35 mi. That is"
        " 31 features, 144.98 mi. Own geometry (AVAILABLE, not loaded): 19 GeoJSON files loaded by "
        "`/trail-guide/`, e.g. `https://mdhta.com/wp-content/uploads/2015/07/mdht-minified-2025-1.geojson` "
        "(114,768 B, Last-Modified 2025-07-25). `coal-creek-loop-minified-2025-3` and "
        "`white-butte-minified-2025-2` are also 2025; the other 16 date from 2016. Each trail page has "
        '"Download GPX".',
    ),
    where=(
        "https://mdhta.com/wp-content/uploads/2015/07/mdht-minified-2025-1.geojson",
        "https://mdhta.com/",
    ),
    reason="drawn from usfs/'s resources, extracted once there (decision 34); checked names the layer this org's data arrives in",
)
