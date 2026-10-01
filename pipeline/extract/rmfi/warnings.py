"""Rocky Mountain Field Institute: warnings, published, and not landed (coverage audit 2026-10-01,
batch p07_persist).

Licence: as above. Folders: `usfs`, `cpw`.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'Pike-San Isabel alerts: "Forest Order #02-12-03-23-17 Food Storage Prohibitions on Pike-San Isabel '
        'National Forests" (2023-08-02; I read the title, not the order text), and the page\'s "Fire Danger '
        "Status\" block. CPW's standing layers (b7, Measured there): `CPWAdminData/6` GMU (Big Game), 186 "
        "polygons, and `CPWSpeciesData/20` Black Bear Human Conflict Area, 613 polygons. Tried: as for "
        "closures.",
    ),
    where=("https://rmfi.org/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
