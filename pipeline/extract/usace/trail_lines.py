"""US Army Corps of Engineers: trail lines, published, and not landed (coverage audit 2026-10-01, batch
c9_federal_state_rest).

As the row says, nothing national. RIDB has no centerlines.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "District layers only. Mobile District: "
        "`services2.arcgis.com/sdTb0lsRURdKFejG/.../Trails_Public_View/FeatureServer/0`, 149 lines, plus 80 "
        "trail-feature points on layer 1. Tulsa District: "
        "`services8.arcgis.com/GvI5dZtQIoT0Fznq/.../District_Recreation_Features_SWT/FeatureServer/13`, 6 "
        "lines.",
    ),
    where=("https://usace.army.mil/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
