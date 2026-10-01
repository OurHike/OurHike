"""Dartmouth Outing Club: warnings, nothing published (coverage audit 2026-10-01, batch p09_persist).

Folders: `usfs/`, `nps/`, an NH Fish & Game folder (name Reasoned).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Same checks. WMNF's `pemigewasset-wilderness-food-storage-requirement` and "
        "`town-hall-road-camping-and-fire-restrictions` do not cover DOC's section: the Pemigewasset Wilderness"
        " lies east of Kinsman Notch (Reasoned from geography). The APPA caution is in Virginia. NH Fish & Game"
        " `WMU/FeatureServer` (item `e15cde961cd64ec5bdfd225907f29796`, edited 2026-08-26) gives hunting-unit "
        "geography, not season dates.",
    ),
    where=(
        "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services",
        "https://services9.arcgis.com/Nb3RpWJ36xRlYQj2/arcgis/rest/services",
        "https://dartmouth.edu/",
    ),
)
