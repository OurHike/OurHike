"""Great Western Trail Association: warnings, drawn from another folder's resource (decision 53 phase
B, 2026-10-03).

This club's warnings arrive through usfs/ `usfs_r03_fire_restrictions`; _shared/utah_ffsl/
`utah_ffsl_fire_restrictions`, each extracted once in its steward's folder (decision 34). Its
portion is assigned in dbt.

Before decision 53 phase B, 2026-10-03, this note read:

Great Western Trail Association: warnings, published, and not landed (coverage audit 2026-10-01,
batch p01_persist).

Licence: USFS public domain (federal work). Utah FFSL: "The data… are provided 'as is' and 'as
available', with no guarantees…", a disclaimer (none_stated). BLM AZ: none_stated (empty). Not
drought. Folders: `usfs/`, `blm/`, and a Utah FFSL source (there is no catalogue row; `utah-sgid` is
…

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 3),
    checked=(
        "via usfs/ `usfs_r03_fire_restrictions`; _shared/utah_ffsl/ `utah_ffsl_fire_restrictions` (decision 53 phase B, 2026-10-03): `usfs_r03_fire_restrictions` reads `r03/r03_FireRestriction_01/MapServer/0`; `utah_ffsl_fire_restrictions` reads `Fire_Restrictions/FeatureServer/0`",
        "Fire danger:",
        "R4 ForestOrder above: Fire Restriction Stage 1: 3, Stage 2: 1, Firearm Restriction 3.",
        'R3 `r03/r03_FireRestriction_01/MapServer/0`: 1 polygon ("Fire Restriction Orders for the Southwestern Region… includes Fire Restrictions and Closures").',
        "Utah FFSL `Fire_Restrictions/FeatureServer/0` (item `532c79fe…`, owner `FireFFSL`): 176 polygons, last edit 2026-09-30. Multi-agency `Agency` values: FFSL 69, USFS 45 (+1), BLM 32, NPS 23, Navajo 4, Ute 2. `RestrictionType`: Stage 1 72, Stage 2 65, Special Order 18, Closure 10, NPS Order 6, Prevention Order 5. `Status`: Active 13 …",
    ),
    where=(
        "https://apps.fs.usda.gov/fsgisx02/rest/services/r03/r03_FireRestriction_01/MapServer/0",
        "https://services.arcgis.com/ZzrwjTRez6FJiOq4/arcgis/rest/services/Fire_Restrictions/FeatureServer/0",
    ),
    reason="drawn from usfs/'s and _shared/utah_ffsl/'s resources, extracted once there (decision 34); checked names the layers this org's data arrives in",
)
