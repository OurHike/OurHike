"""Alaska Trails: warnings, drawn from nps/warnings.py's NPS alerts resource (decision 53, phase B,
2026-10-03).

NPS's alerts for park codes `dena` and `kefj` land once, in nps/warnings.py's `nps_alerts`, whose
sources.json entry lists them against this folder in `park_codes` (decision 34). NPS's Danger,
Caution and Information categories are the warnings half, split from the rest in dbt.

The inventory also found a web page, an ArcGIS layer for this club, which other phase B readers
take; if one lands for this type it takes this file, and this note becomes a line in its docstring.

The coverage audit's note, kept as it was (restated from reference/org_coverage.json, whose text is
trimmed where it ends in '…'):

These are planning records (they carry a `Cost` field), but "impassable crossing" is a hazard point
all the same.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 3),
    checked=(
        (
            "NPS alerts API, `parkCode=dena,kefj` (the decision 53 inventory, batch 3, 2026-10-03): 2 (Park "
            "Closure 'Teklanika Area Closures' 2026-09-24; Information 'Road Open To: Mile 30'). NPS manages 8 "
            "AKLT segments. Landed by nps/warnings.py as nps_alerts."
        ),
        (
            "(coverage audit, 2026-10-01) `AKLT_Trail_Obstacles/FeatureServer/20`: 13 points, last edit "
            "2026-03-05: `BridgeNeeded(Impassable)` 4, `BridgeNeeded(Passable)` 7, `RiverFord` 2. "
            "`Seward_to_Eagle_River_Obstacles/2`: 7 (2023-05-17)."
        ),
    ),
    where=(
        "https://developer.nps.gov/api/v1/alerts?parkCode=dena,kefj",
        "https://services.arcgis.com/E4aLbdRuC2azR6Sw/arcgis/rest/services/AKLT_Trail_Obstacles/FeatureServer/20",
    ),
    reason=(
        "drawn from nps/'s resources, extracted once there (decision 34); checked names the layer this org's data arrives in"
    ),
)
