"""Volunteers for Outdoor Colorado: trail lines, nothing published (coverage audit 2026-10-01, batch
p03_persist).

none_stated on the DU layers: `licenseInfo` and `copyrightText` are both empty. They are not hiker
data in any case.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'VOC appears in GIS in one place only. Two DU GIS student StoryMaps (`ba49b60f…` "Volunteers for '
        'Outdoor Colorado: Statewide Impact" and `2ead45ee…` "VOC\'s Impact in Colorado", owner `an email '
        "address`) embed web maps `c21baae8…`, `408bf0a5…` and `f14b9427…`. Those web maps draw on "
        "`services1.arcgis.com/44C95LOqZjbh8Row/arcgis/rest/services/VOC_Volunteer_Projects`, `VOC_Projects` "
        "and `VOC_Training_Projects` (FeatureServer/1). Each layer is 64 polygons, Colorado's counties, with "
        "project-count fields (`training`, `total_volunteer_projects`, `public_projects` …), last edited "
        "2025-08-15. There are …",
    ),
    where=(
        "https://services1.arcgis.com/44C95LOqZjbh8Row/arcgis/rest/services/VOC_Volunteer_Projects",
        "https://voc.org",
        "https://voc.org/",
    ),
)
