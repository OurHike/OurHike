"""Rocky Mountain Field Institute: trail lines, drawn from another folder's resource (coverage audit
2026-10-01, batch p07_persist).

Licence: the City's "Trails" item has an empty licenseInfo (none_stated). But the City's MapServer
item for the same family of layers (`9f5d0bb4…`) carries an explicit restriction (see the end of
this file), and El Paso County's does too. b7 has already said the loaded snapshot is Boulder
County's …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Loaded `cotrex_trails` "
        "(`services3.arcgis.com/0jWpHMuhmHsukKE3/.../CPW_Trails_08222024/FeatureServer/2`), in the Pikes Peak "
        "envelope: 1,301 segments managed by City of Colorado Springs Parks, 268 by USFS Pikes Peak Ranger "
        "District, 186 by El Paso County Parks, 61 Cheyenne Mountain SP, 31 City of Manitou Springs. Fresher "
        "land-manager sources: the City's \"Trails\" FeatureServer/6 (2,470 lines, 2026-02-12); CPW's own "
        "`CPWAdminData/FeatureServer/15` (2026-08-27, per b7); El Paso County `HubPublic/Trails` (425). The "
        "only RMFI-named GIS is the City's project work log (305 lines). Tried: (1) rmfi.org …",
    ),
    where=(
        "https://services5.arcgis.com/ttNGmDvKQA7oeDQ3/arcgis/rest/services/CPWAdminData/FeatureServer/15",
        "https://rmfi.org",
    ),
    reason="drawn from another folder's resource, extracted once there (decision 34); checked names it",
)
