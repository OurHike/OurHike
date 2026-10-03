"""Save Mount Diablo: warnings, published, and not landed (coverage audit 2026-10-01, batch
p06_persist).

Licence: attribution_only. licenseInfo is empty; copyrightText is "East Bay Regional Park District".
Folders: `ebrpd/`; WFIGS goes in `_shared/nifc/` (new, Reasoned). Today's Level 2 status is not in
the layer. Where EBRPD publishes it is UNKNOWN.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

ArcGIS layers read and not wired as closures or warnings (decision 53 phase B, 2026-10-03):
https://services2.arcgis.com/jeEP9c9zZoQQwtck/arcgis/rest/services/Fire_Warning_Extreme_Danger_Level_2/FeatureServer/6,
EBRPD's 132 areas that close at fire-danger Level 2, last edited 2023-08-23: a standing map, not
today's level, which EBRPD publishes elsewhere (UNKNOWN where).
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`services2.arcgis.com/jeEP9c9zZoQQwtck/arcgis/rest/services/Fire_Warning_Extreme_Danger_Level_2/FeatureServer/6`:"
        " 132 polygons, 29 in the box. Fields: `NAME`, `STATUS`, `Fire_Danger_Rating_Area`, "
        "`Fire_Danger_Level_2`. Data last edited 2023-08-23. It is a standing map of which areas close at Level"
        " 2, not today's level. For live fire, NIFC's WFIGS perimeters (see `onda`). Tried: 1–6 above.",
    ),
    where=(
        "https://services2.arcgis.com/jeEP9c9zZoQQwtck/arcgis/rest/services/Fire_Warning_Extreme_Danger_Level_2/FeatureServer/6",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
