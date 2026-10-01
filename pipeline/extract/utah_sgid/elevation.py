"""Utah UGRC — SGID Trails and Pathways: elevation, published, and not landed (coverage audit
2026-10-01, batch b7_long_trails_states).

A derivative of the USGS and state lidar the shared elevation source already covers.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "UGRC redistributes DEMs: `USGS_DEMs_gdb/0` (98-tile index, last edit 2025-09-23), "
        "`AutoCorrelated_DEMs_gdb`, `Contours`.",
    ),
    where=(
        "https://services1.arcgis.com/99lidPhWCzftIe9K/ArcGIS/rest/services",
        "https://gis.utah.gov/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
