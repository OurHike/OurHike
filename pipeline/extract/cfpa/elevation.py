"""Connecticut Forest & Park Association: elevation, drawn from CT DEEP's blue-blazed trail layer, extracted in ct_deep/.

CFPA stewards the Blue-Blazed Hiking Trails, and the only elevation figures
on them are the `Gains` and `Losses` columns of CT DEEP's
`BlueBlazedHikingTrails/0`, which ct_deep/trail_lines.py extracts as
`ct_deep_blue_blazed` and ct_deep/elevation.py shares (decision 34: one
upstream, one resource). Their unit and method are unstated, so they stay
@unvalidated until compared with 3DEP over the same lines (ct_deep's note).
CFPA's own current layer has no elevation at all.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 3),
    checked=(
        "CT DEEP's `BlueBlazedHikingTrails/0` (read 2026-10-03): 351 polylines, hasZ false, integer `Gains` and "
        "`Losses` fields, dataLastEditDate 2024-05-17; registered as `ct_deep_blue_blazed`",
        "CFPA's own `BBHT_Public_Map_Trails/0` (read 2026-10-03): 848 polylines, edited 2026-09-29, hasZ false and "
        "no gain, loss or elevation field",
        "coverage audit (2026-10-01, batch c10_nst_rest): CFPA's other layers have hasZ false, and nothing in "
        "pipeline/ reads Gains or Losses",
    ),
    where=(
        "https://services1.arcgis.com/FjPcSmEFuDYlIdKC/arcgis/rest/services/BlueBlazedHikingTrails/FeatureServer/0",
        "https://services7.arcgis.com/nYjAANwm3YtNiTFR/arcgis/rest/services/BBHT_Public_Map_Trails/FeatureServer/0",
        "https://ctwoodlands.org/",
    ),
    reason="drawn from another folder's resource, extracted once there (decision 34); checked names it",
)
