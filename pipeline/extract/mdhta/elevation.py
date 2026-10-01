"""Maah Daah Hey Trail Association: elevation, published, and not landed (coverage audit 2026-10-01,
batch c8_regional_5).

Whether Z comes from GPS or a DEM is `@unvalidated`. Settle it by comparing a sample with 3DEP.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "The GeoJSON vertices are 3-D. The first vertex of `mdht-minified-2025-1` is `[-103.4449419, "
        "46.5982664, 774.478]`, and `long-x-1` starts at 782.28. Trail pages render an "
        "`elevation-profile-holder`.",
    ),
    where=(
        "https://apps.fs.usda.gov/arcx/rest/services",
        "https://mdhta.com/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
