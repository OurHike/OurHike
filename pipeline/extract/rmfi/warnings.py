"""Rocky Mountain Field Institute: warnings, published, and not landed (coverage audit 2026-10-01,
batch p07_persist).

Licence: as above. Folders: `usfs`, `cpw`.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Decision 53 phase B (2026-10-03): the Pike and San Isabel alerts page lands once, in usfs/closures.py
as `usfs_r02_psicc_alerts`, which the warnings staging model reads too, so this note now names it as
where RMFI's warnings arrive. The City of Colorado Springs' page has no recorded URL (closures.py says
why it is not read).
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 3),
    checked=(
        "via usfs/closures.py `usfs_r02_psicc_alerts` (decision 53 phase B, 2026-10-03): its fire-restriction and caution cards are this type's.",
        'Pike-San Isabel alerts: "Forest Order #02-12-03-23-17 Food Storage Prohibitions on Pike-San Isabel '
        'National Forests" (2023-08-02; I read the title, not the order text), and the page\'s "Fire Danger '
        "Status\" block. CPW's standing layers (b7, Measured there): `CPWAdminData/6` GMU (Big Game), 186 "
        "polygons, and `CPWSpeciesData/20` Black Bear Human Conflict Area, 613 polygons. Tried: as for "
        "closures.",
    ),
    where=(
        "https://www.fs.usda.gov/r02/psicc/alerts",
        "https://rmfi.org/",
    ),
    reason="drawn from usfs/'s resources, extracted once there (decision 34); checked names the page this org's warnings arrive in",
)
