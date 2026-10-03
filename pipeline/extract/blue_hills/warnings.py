"""Friends of the Blue Hills: warnings, drawn from another folder's resource (decision 53 phase B,
2026-10-03).

This club's warnings arrive through _shared/ma_dcr/ `ma_dcr_blue_hills_hunt_areas`, each extracted
once in its steward's folder (decision 34). Its portion is assigned in dbt.

DCR's notices for the reservation are mass.gov's per-park alerts fragment
(https://www.mass.gov/alerts/page/14961, the node the park page
https://www.mass.gov/locations/blue-hills-reservation loads; 1 item on 2026-10-03, an event notice
'Updated Sep. 24, 2026'). It is DCR's, read once in _shared/ma_dcr/ as `ma_dcr_blue_hills_alerts`
(decision 34). mass.gov's terms ("the Commonwealth forbids any copying or use other than 'fair
use'") restrict copying, not reading: decision 55's case. Friends of the Blue Hills' WordPress has
13 categories and none for closures or alerts, so its feed (https://friendsofthebluehills.org/feed/)
is not read: choosing its 'TRAIL ALERT!!' posts out of the blog would be prose parsing.

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
    where=(
        "https://services1.arcgis.com/7iJyYTjCtKsZS1LR/arcgis/rest/services/HuntAreas_BH_PGC_FM/FeatureServer/18",
        "https://www.mass.gov/alerts/page/14961",
    ),
    reason="drawn from _shared/ma_dcr/'s resources, extracted once there (decision 34); checked names the layers this org's data arrives in; and from its mass.gov fragment, `ma_dcr_blue_hills_alerts`",
)
