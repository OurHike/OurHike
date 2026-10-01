"""US Army Corps of Engineers: warnings, published, and not landed (coverage audit 2026-10-01, batch
c9_federal_state_rest).

One district.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Omaha District "
        "`services5.arcgis.com/6AHfZAoqk1VUqQpS/.../GarrisonHuntingAndTrappingRestrictions20260424/FeatureServer`"
        " (hunting and trapping restrictions 2026, Lake Sakakawea / Garrison). Skeptic counted it: layer 21 "
        '"Restriction", 24 polygons (`Restriction`, `AreaName`, `AreaDescription`, `ContactOffice`), last '
        "edited 2026-05-29.",
    ),
    where=("https://usace.army.mil/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
