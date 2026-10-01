"""Forest Park Conservancy: trail lines, published, and not landed (coverage audit 2026-10-01, batch
p07_persist).

Licence: the Portland metadata (`portlandmaps.com/metadata/…LayerID=52963`) reads "Access
Constraints: Available for Public Use. Use Constraints: These data are distributed under the terms
of the City of Portland Data Distribution Policy. Care was taken in the creation of this data but it
is …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "City of Portland Open Data: "
        '`https://www.portlandmaps.com/od/rest/services/COP_OpenData_Environment/MapServer/27` "Parks Trails" '
        '(item `6a1520f9…`, modified 2024-09-12, 14,221 views, copyrightText "Bureau of Parks and Recreation"):'
        " 2,558 lines. Forest Park (layer 35, `PROPERTYID` 127, 5,110 acres) has 253 segments, 78.23 mi. By "
        "TYPE: Trail/Path 125, Firelane 60, CAT Road (retired) 52, Maintenance Road 13.; Also: PP&R's own "
        "`services.arcgis.com/quVN97tn06YNGj9s/arcgis/rest/services/PPR_Trails/FeatureServer/0` (2,904 lines; "
        "Forest Park: existing 257, informal 5; last edit 2024-01-10). Oregon …",
    ),
    where=(
        "https://www.portlandmaps.com/od/rest/services/COP_OpenData_Environment/MapServer/27",
        "https://services.arcgis.com/quVN97tn06YNGj9s/arcgis/rest/services/PPR_Trails/FeatureServer/0",
        "https://services2.arcgis.com/McQ0OlIABe29rJJy/arcgis/rest/services/Trails/FeatureServer/0",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
