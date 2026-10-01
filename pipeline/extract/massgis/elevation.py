"""MassGIS (Bureau of Geographic Information): elevation, published, and not landed (coverage audit
2026-10-01, batch b5_nyc_nj_ct_ma_pa).

Built from the same 2013–2021 lidar collections 3DEP serves (Reasoned). Goes in `_shared/`, low
priority.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`LiDAR/DEM_lidar_2013to2021_32bitFloat/ImageServer` (pixel 1.38 in EPSG:3857), "
        "`LiDAR/ShadedRelief_LiDAR_2013to2021`, `AGOL/Contours_1Foot`, `AGOL/Lidar_DEM_Mosaic_Index`.",
    ),
    where=("https://arcgisserver.digital.mass.gov/arcgisserver/rest/services/LiDAR/DEM_lidar_2013to2021_32bitFloat/ImageServer",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
