"""USDA Forest Service: warnings, published, and not landed (coverage audit 2026-10-01, batch
b6_federal).

A BAER polygon marks a recent burn (hazard trees, debris flow). That is a hazard area, but it is not
a notice. Reasoned, not published by USFS as a warning.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'Per-forest alerts pages carry an "Alerts Key" (Critical / Fire Restriction / Caution / Information). '
        'Cherokee today: "Fire Restrictions Continue Along the Appalachian Trail", "Roan Mountain Fire '
        'Restrictions". `.../EDW/EDW_BurnedAreaEmergencyResponse_01/MapServer/0` (BAER assessment boundaries, '
        "polygon): 246, ignitions 2024-03-22 → 2026-08-26, `max(etl_modified_date)` 2026-09-30, 124 since "
        "2025-01-01. Regional fire-restriction layers: `fsgisx02/.../r03/r03_FireRestriction_01/0` (1 polygon),"
        " `PSICCRangerDistrictsFireRestrictions_2026` (R02, 2026-06-25). WFAS (`https://www.wfas.net/`, titled "
        "…",
    ),
    where=(
        "https://www.wfas.net/",
        "https://apps.fs.usda.gov/arcx/rest/services",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
