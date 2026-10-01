"""Buckeye Trail Association: trail lines, published, and not landed (coverage audit 2026-10-01, batch
c8_regional_5).

Restricted. The NPS portion is NPS's own public-domain data and unaffected. Using ODNR's copy is a
maintainer decision (above).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "BTA's own: "
        "`https://services.arcgis.com/VV0wGgcoagcH1JO8/arcgis/rest/services/BT_trail_line_updated/FeatureServer/0`,"
        ' 501 polylines, last edited 2022-05-25. Its description says "Data is only updated once a year"; '
        '`licenseInfo` says "Permission from the Buckeye Trail Assocation is required before use!" Older: '
        '`bt_web_2016` (6 features, "as of 03/01/2020"). ODNR copy: `ODNR_Trails/MapServer/2`, 1 feature, '
        '1,288.70 mi. Partly LOADED: `nps_trails` holds 35 CUVA features named "Buckeye Trail…". `usfs_trails` '
        "holds 0 in Wayne NF.",
    ),
    where=("https://services.arcgis.com/VV0wGgcoagcH1JO8/arcgis/rest/services/BT_trail_line_updated/FeatureServer/0",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
