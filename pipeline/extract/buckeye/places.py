"""Buckeye Trail Association: places, published, and not landed (coverage audit 2026-10-01, batch
c8_regional_5).

Restricted.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        '24 Trail Town pages (`/towns`, "listed in clockwise order … starting with Mentor"). 26 sections, each '
        "with counties, abutting sections and per-county sheriff and highway-patrol numbers. "
        "`retail_map_outline_bt/FeatureServer/0`: 26 section polygons (2020-04-01).",
    ),
    where=("https://services.arcgis.com/VV0wGgcoagcH1JO8/arcgis/rest/services/retail_map_outline_bt/FeatureServer/0",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
