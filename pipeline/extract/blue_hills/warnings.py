"""Friends of the Blue Hills: warnings, drawn from another folder's resource (decision 53 phase B,
2026-10-03).

This club's warnings arrive through _shared/ma_dcr/ `ma_dcr_blue_hills_hunt_areas`, each extracted
once in its steward's folder (decision 34). Its portion is assigned in dbt.

Other sources still to wire (decision 53 phase B, 2026-10-03; the phase A inventory has each one's
robots.txt, terms and change check): https://www.mass.gov/alerts/page/14961 (html_page);
https://www.mass.gov/locations/blue-hills-reservation (html_page);
https://friendsofthebluehills.org/feed/ (rss);
https://friendsofthebluehills.org/wp-json/wp/v2/categories?per_page=100&_fields=id,name,slug,count
(wordpress).

Before decision 53 phase B, 2026-10-03, this note read:

Friends of the Blue Hills: warnings, published, and not landed (coverage audit 2026-10-01, batch
c4_regional_1).

Hunting is in scope for warnings. This is ArcGIS and current.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 3),
    checked=(
        "via _shared/ma_dcr/ `ma_dcr_blue_hills_hunt_areas` (decision 53 phase B, 2026-10-03): `ma_dcr_blue_hills_hunt_areas` reads `HuntAreas_BH_PGC_FM/FeatureServer/18`",
        'DCR\'s "Blue Hills Hunt Areas", `https://services1.arcgis.com/7iJyYTjCtKsZS1LR/arcgis/rest/services/HuntAreas_BH_PGC_FM/FeatureServer/18`: 13 polygons, YrHuntArea, lastEdit 2026-07-28. Plus "Clipped Wildlife Management Zones". FBH posts each year on "White-Tailed Deer Management Program 2025" and "Traffic Advisory Related to Controlled Deer Hunt".',
    ),
    where=("https://services1.arcgis.com/7iJyYTjCtKsZS1LR/arcgis/rest/services/HuntAreas_BH_PGC_FM/FeatureServer/18",),
    reason="drawn from _shared/ma_dcr/'s resources, extracted once there (decision 34); checked names the layers this org's data arrives in; the org's own non-ArcGIS sources are listed in the docstring, still to wire",
)
