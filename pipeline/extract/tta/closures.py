"""Tennessee Trails Association: closures, nothing published (coverage audit 2026-10-01, batch
p09_persist).

TDEC layer licenseInfo was not re-read here; see c9. Folders: `tn-state-parks/`, `usfs/`, `nps/`.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "TTA sends hikers to the land manager (audit). The land managers' channels today: TDEC "
        "`https://services5.arcgis.com/bPacKTm9cauMXVfn/arcgis/rest/services/TDEC_Trail_Closures_Public/FeatureServer/0`,"
        " 22 closed segments, last edit 2026-09-30 19:50 UTC (re-counted); Cherokee NF alerts page "
        "`https://www.fs.usda.gov/r08/cherokee/alerts` (HTML), 16 alert links, e.g. "
        '`citico-creek-flood-closure`; NPS alerts API for GRSM, 3 alerts (2 "Park Closure", 1 "Information"). '
        "Tried: (2) AGOL and Hub as above; (3) TNMap; (4) the three land managers above; (5) data.gov and "
        "Socrata; (7) TTA's own conditions …",
    ),
    where=(
        "https://services5.arcgis.com/bPacKTm9cauMXVfn/arcgis/rest/services/TDEC_Trail_Closures_Public/FeatureServer/0",
        "https://www.fs.usda.gov/r08/cherokee/alerts",
        "https://data.gov",
    ),
)
