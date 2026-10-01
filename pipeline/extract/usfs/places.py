"""USDA Forest Service: places, published, and not landed (coverage audit 2026-10-01, batch
b6_federal).

No editingInfo (on-prem server).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "EDW layer 0 of each: `ForestSystemBoundaries_01` 112, `RangerDistricts_03` 503, `Wilderness_02` 449, "
        "`NationalGrassland_01` 20, `OtherNationalDesignatedArea_01` 227, `SpecialInterestManagementArea_01` "
        "1,906 (all polygon).",
    ),
    where=("https://apps.fs.usda.gov/arcx/rest/services",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
