"""Utah UGRC — SGID Trails and Pathways: warnings, published, and not landed (coverage audit
2026-10-01, batch b7_long_trails_states).

The forecasts themselves are the Utah Avalanche Center's.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

ArcGIS layers read and not wired as closures or warnings (decision 53 phase B, 2026-10-03):
https://services1.arcgis.com/99lidPhWCzftIe9K/ArcGIS/rest/services/recreation_avalanche_center_forecast_zones/FeatureServer/0,
9 static zones linking to the Utah Avalanche Center's forecasts; the forecasts are UAC's, a _shared/
question;
https://services1.arcgis.com/99lidPhWCzftIe9K/ArcGIS/rest/services/Utah_Fire_Restriction_Areas_Lookup/FeatureServer/0,
a 19-row lookup table last edited 2020-09-28, not restrictions; FFSL's live layer is
_shared/utah_ffsl/.
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
