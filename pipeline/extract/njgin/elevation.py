"""NJDEP / NJGIN — Statewide Trails: elevation, published, and not landed (coverage audit 2026-10-01,
batch b5_nyc_nj_ct_ma_pa).

1:100,000 grids are far coarser than 3DEP. Not worth loading for profiles. The trail grade fields
are the only trail-specific product, and they cover 9% of segments. NJ's statewide lidar is
published by NJOGIS (Treasury), not NJDEP, so it belongs in `_shared/` (Reasoned).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'NJGWS DGS99-4 "Digital Elevation Grids for New Jersey (1:100,000 scale)", a zip at '
        "`https://nj.gov/dep/gis/digidownload/zips/OpenData/njgws/dgs99-4.zip` (item modified 2023-04-12). "
        "DGS00-3 topographic contours (1:100,000). The hosted trails layer's `grade_max`/`grade_mean` are "
        "populated on 270 of 3,068 segments. `Publicly_Accessible_High_Elevation_Points_in_New_Jersey/11` holds"
        " 21 points (edited 2024-07-24).",
    ),
    where=(
        "https://nj.gov/dep/gis/digidownload/zips/OpenData/njgws/dgs99-4.zip",
        "https://mapsdep.nj.gov/arcgis/rest/services",
        "https://services1.arcgis.com/QWdNfRs7lkPq4g4Q/arcgis/rest/services",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
