"""NYC Department of Transportation: points of interest, published, and not landed (coverage audit
2026-10-01, batch b5_nyc_nj_ct_ma_pa).

Bridges matter: they are where a greenway crosses a highway or water. The AGOL items carry a
disclaimer and no grant (see Terms). Skeptic, 2026-10-01: the 66 in parks are not all of DOT's
pedestrian bridges. The same org holds `Ped_DOT_Bridges_View/FeatureServer/0` (59),
`Ped_Ferry_Bridges_View` …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`https://services.arcgis.com/wmZOI9vyUBq1zTZx/arcgis/rest/services/Ped_Bridges_In_Parks%20_View/FeatureServer/0`:"
        " 66 points, pedestrian bridges in parks, fields `FEATURE_CA`/`FEATURE_CR` (carried/crossed), last edit"
        " 2025-11-14. `Bridges_In_Parks_View`: 132. `WalkNYC Sign Locations` `ns8x-qshd`: 980, of which "
        '"Greenway (A)" 9 and "Fingerpost" 23. `Seating Locations` `esmy-s8q5`: 3,622 benches. DOT/JCDecaux '
        "toilets are already inside `nyc_public_restrooms`.",
    ),
    where=(
        "https://services.arcgis.com/wmZOI9vyUBq1zTZx/arcgis/rest/services/Ped_Bridges_In_Parks%20_View/FeatureServer/0",
        "https://data.cityofnewyork.us/d/ns8x-qshd",
        "https://data.cityofnewyork.us/d/esmy-s8q5",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
