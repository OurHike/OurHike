"""Utah UGRC — SGID Trails and Pathways: warnings, published, and not landed (coverage audit
2026-10-01, batch b7_long_trails_states).

The forecasts themselves are the Utah Avalanche Center's.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`recreation_avalanche_center_forecast_zones/0`: 9 polygons with `forecast_link`, last edit 2026-03-07."
        " `Utah_Fire_Restriction_Areas_Lookup/0`: a 19-row table, last edit 2020-09-28 (stale).",
    ),
    where=(
        "https://services1.arcgis.com/99lidPhWCzftIe9K/ArcGIS/rest/services",
        "https://gis.utah.gov/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
