"""Oregon Natural Desert Association: closures, published, and not landed (coverage audit 2026-10-01,
batch p06_persist).

USFS R6 licence: disclaimer only ("The USDA Forest Service makes no warranty… Natural hazards may or
may not be depicted on the data and maps, and land users should exercise due caution."). It is
public domain under 17 U.S.C. §105 (maintainer, 2026-09-02, `usfs_licence`).; BLM licence: …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "USFS Region 6 "
        "(`services1.arcgis.com/gGHDlz6USftL5Pau/arcgis/rest/services/R06_FireClosureOrders_PublicView/FeatureServer`,"
        " item `35b11d7829c94594a788e79d1cc327ff`, owner `USFSRegion06`; already in audit b6 for `usfs/`):",
        "2,068 points, 10,509 lines, 547 polygons; dataLastEditDate 2026-09-23",
        "Polygons with `ClosureStatus='Active'`: 15 (group-by over 547). Fremont-Winema has 1 active polygon "
        "(Wright Springs Forest Closure, 2026-09-07 to 2026-10-31).",
        'Active features in an ODT box (-121.4,42.4 to -117.0,44.5): 1 point (Ochoco NF, "Closure of Wiley Flat'
        ' Campground"), 0 lines, 0 polygons. …',
    ),
    where=(
        "https://services1.arcgis.com/gGHDlz6USftL5Pau/arcgis/rest/services/R06_FireClosureOrders_PublicView/FeatureServer",
        "https://services1.arcgis.com/KbxwQRRfWyEYLgp4/arcgis/rest/services/OregonRecreationStatusWebmap20210428/FeatureServer/0",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
