"""Wisconsin DNR Open Data: closures, published, and not landed (coverage audit 2026-10-01, batch
b7_long_trails_states).

The public view exposes `Reporter_email` and `Internal_Contact`, which are staff addresses. Drop
those columns at extract. `Impact=Low` rows are candidates for warnings under decision 7. Skeptic
adds a terms finding (Measured, item `2a0f013583dc452e938aead18cbf71f3` "PR: WI Park Closures PUBLIC
…

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`WI_Park_Closures_PUBLIC_VIEW/FeatureServer/0`: 69 points, all `Active_Flag = Yes` (Impact High 25, "
        "Moderate 16, Low 28). Fields: `Closure_Name`, `Reason`, `Description`, `Exp_End_Date`; last edit "
        '2026-09-29. Example: "Governor Knowles SF Cedar Hiking Trail Section From Mile 25 to 26 Closed", storm'
        " damage. Also `LF_DNR_MGD_PROP_WTM_Ext/6`: 1 closed-area polygon (`CLOSE_DATE` 2016-03-08).",
    ),
    where=(
        "https://services5.arcgis.com/Ul9AyFFeFTjf08DW/arcgis/rest/services/WI_Park_Closures_PUBLIC_VIEW/FeatureServer/0",
        "https://dnrmaps.wi.gov/arcgis/rest/services",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
