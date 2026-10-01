"""Appalachian Mountain Club: trail lines, drawn from another folder's resource (coverage audit
2026-10-01, batch c10_nst_rest).

This is the White Mountain inventory with maintainers. It covers every club, so the one layer feeds
RMC, WODC, CTA and DOC credit too. `New_Hampshire_Trails` (2,982) and `Maine_Trails` (966) are
compilations with a `Source` column, not AMC's own work.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Arrives in three ways. Via `atc`: `centerline` for the A.T. sections. Via `usfs_trails`: the WMNF. Via"
        ' `massgis_long_distance_trails`: 19 features named "New England Trail". AMC\'s own: '
        "`https://services9.arcgis.com/mxpFc8oFRyNIV03y/arcgis/rest/services/wmnf_regional_trails_2_2024/FeatureServer/0`"
        " (item `f8b38940a5b54a8485a4c2196da68ad7`, public, owner a personal ArcGIS account, no licence text): "
        "1,672 segments, 1,366.3 mi, last edit 2026-05-26. `Maintainer`: WMNF 431 segments (534.9 mi), AMC 385 "
        "(309.1 mi), RMC 220 (91.1 mi), NHDP 82, WODC 60, SLA 53, CTA 52, DOC 24, MATC 17. `AT` = y on 167 …",
    ),
    where=(
        "https://services9.arcgis.com/mxpFc8oFRyNIV03y/arcgis/rest/services/wmnf_regional_trails_2_2024/FeatureServer/0",
        "https://outdoors.org/",
    ),
    reason="drawn from atc/'s resources, extracted once there (decision 34); checked names the layer this org's data arrives in",
)
