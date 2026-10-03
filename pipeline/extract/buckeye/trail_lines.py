"""Buckeye Trail Association: trail lines, published, and refused by the layer's own terms.

BTA's own layer asks for permission before use, in its licenseInfo (quoted in `terms`, re-read live on
2026-10-03 with the layer's metadata, count, extent and one statistics query), and `buckeye` is one of
the four refuse rows, so it loads on written permission and not before (rule 7; the poll: "note now,
load on permission"). The NPS portion is NPS's own public-domain data and unaffected: `nps_trails` holds 35
CUVA features named "Buckeye Trail". Using ODNR's copy (`ODNR_Trails/MapServer/2`, one 1,288.70-mile
line) is a maintainer decision, an agency's copy of a steward's gated route.

Not the same case as places.py, which extracts the Association's retail map outlines under decision
39: that layer states nothing, so decision 39 counts it as published and rule 7 keeps it off phones. This
one states its own condition, and a layer's own terms are never routed around.

The coverage audit's evidence, restated from reference/org_coverage.json, is the second `checked` item.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 3),
    checked=(
        "Live read 2026-10-03 (decision 54, wave 1): BT_trail_line_updated/FeatureServer/0 still answers "
        "anonymously, 501 polylines (returnCountOnly), dataLastEditDate 2022-05-25, fields Website, "
        "OBJECTID, Shape__Len, OBJECTID_1 and Shape__Length; its item's licenseInfo reads, whole, "
        '"Permission from the Buckeye Trail Assocation is required before use!" and its '
        'accessInformation "Buckeye Trail Association". No sources.json row registers it. One page of its '
        "attributes (501 rows, no geometry) was also read, by mistake, at 15:51:34Z the same day, and deleted "
        "from the session's cache unused; nothing from it reached the repository.",
        "BTA's own: "
        "`https://services.arcgis.com/VV0wGgcoagcH1JO8/arcgis/rest/services/BT_trail_line_updated/FeatureServer/0`,"
        ' 501 polylines, last edited 2022-05-25. Its description says "Data is only updated once a year"; '
        '`licenseInfo` says "Permission from the Buckeye Trail Assocation is required before use!" Older: '
        '`bt_web_2016` (6 features, "as of 03/01/2020"). ODNR copy: `ODNR_Trails/MapServer/2`, 1 feature, '
        '1,288.70 mi. Partly LOADED: `nps_trails` holds 35 CUVA features named "Buckeye Trail…". `usfs_trails` '
        "holds 0 in Wayne NF.",
    ),
    where=("https://services.arcgis.com/VV0wGgcoagcH1JO8/arcgis/rest/services/BT_trail_line_updated/FeatureServer/0",),
    terms="Permission from the Buckeye Trail Assocation is required before use!",
    reason=(
        "refused: the layer's own licenseInfo requires permission before use, and buckeye is a refuse row; "
        "it loads on written permission"
    ),
)
