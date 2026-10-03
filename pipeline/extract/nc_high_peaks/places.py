"""NC High Peaks Trail Association: places, nothing published (coverage audit 2026-10-01, batch
p09_persist).

Folders: `nc-dpr/`, `usfs/`.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Land-manager places: NC State Parks `NC_State_Parks_System/FeatureServer/0` (346 park polygons, c9); "
        "the USFS recreation areas in `usfs_rec_sites`. Tried: items 1 to 6 as for POIs.",
    ),
    where=("https://services6.arcgis.com/nRIB86xC7kq6wavB/arcgis/rest/services/NC_State_Parks_System/FeatureServer/0",),
)
