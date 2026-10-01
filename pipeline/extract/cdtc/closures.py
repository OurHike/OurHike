"""Continental Divide Trail Coalition: closures, published, and not landed (coverage audit 2026-10-01,
batch b7_long_trails_states).

The best-shaped feed in this batch. `Type` plus `Active` maps straight onto decision 7's
`obstructs_trail` split, and `Milepost` is present.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`CDT_Alerts_view/FeatureServer/1` Alert Points: 149, with `Active=Yes` on 12 `Closure` and 15 `Alert`."
        " `/2` Alert Lines: 76, with `Active=Yes` on 6 `Closure` and 6 `Alert`. `Area_Closures_view/1`: 4 "
        "polygons, 1 active. `Reroutes_view/1`: 30, 7 active. Last edit 2026-09-24. Page: "
        "`cdtcoalition.org/closures-and-alerts/`.",
    ),
    where=(
        "https://services8.arcgis.com/WyuHwdftppQLa5KO/arcgis/rest/services/CDT_Alerts_view/FeatureServer/1",
        "https://cdtcoalition.org/closures-and-alerts/",
        "https://services.wygisc.org/HostGIS/rest/services",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
