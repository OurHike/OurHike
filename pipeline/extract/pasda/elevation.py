"""PASDA / PA DCNR: elevation, published, and not landed (coverage audit 2026-10-01, batch
b5_nyc_nj_ct_ma_pa).

3DEP covers PA. Load only if it is shown to differ (c9's verdict, kept).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "PAMAP, DCNR's statewide lidar programme, served by PASDA: "
        "`imagery.pasda.psu.edu/arcgis/rest/services/pasda/PAMAP_DEM_mosaic/MapServer`, `PAMAP_Hillshade`. "
        '`pasda/DCNR2/MapServer/3` "Maximum Elevations in Pennsylvania Counties 202207": 67 points.',
    ),
    where=(
        "https://mapservices.pasda.psu.edu/server/rest/services/pasda/DCNR2/MapServer/3",
        "https://imagery.pasda.psu.edu/arcgis/rest/services/pasda/PAMAP_DEM_mosaic/MapServer",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
