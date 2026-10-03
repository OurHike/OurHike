"""Batona Hiking Club: warnings, drawn from another folder's resource (decision 53 phase B,
2026-10-03).

This club's warnings arrive through njgin/ `njdep_fire_danger`, each extracted once in its steward's
folder (decision 34). Its portion is assigned in dbt.

Other sources still to wire (decision 53 phase B, 2026-10-03; the phase A inventory has each one's
robots.txt, terms and change check): https://batona.wildapricot.org/RSS (rss).

Before decision 53 phase B, 2026-10-03, this note read:

Batona Hiking Club: warnings, published, and not landed (coverage audit 2026-10-01, batch
p03_persist).

attribution_only (conditional). The fire-danger item's licenseInfo opens: "This map is provided for
information purposes only and is not monitored 24/7 for accuracy and currency. New Jersey Department
of Environmental Protection (NJDEP) Data Distribution Agreement…". PGC is attribution_only …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 3),
    checked=(
        "via njgin/ `njdep_fire_danger` (decision 53 phase B, 2026-10-03): `njdep_fire_danger` reads `Envr_admin_FFS_danger_public/FeatureServer/2`",
        '`services1.arcgis.com/QWdNfRs7lkPq4g4Q/arcgis/rest/services/Envr_admin_FFS_danger_public/FeatureServer/2`, "NJ Wildfire Danger Level": 3 division polygons with `FIRE_DANGER`, `RECFIRE_RESTRICTION`, `BUILDUP`, `KBDI` and `EditDate`. The Batona Trail lies in CENTRAL NJ (by intersect), which reads LOW with no restriction, edited 2026-09-30. Hunting: `Features/Land/MapServer/67` has `HUNTING_PERMITTED = Yes` on Wharton, Bass River and Brendan T. Byrne state forests. Pennsylvania section: PASDA `PennsylvaniaGameCommission/MapServer/4`, State Game Land 168 (7,800 acres), intersects ATC\'s Batona …',
    ),
    where=("https://services1.arcgis.com/QWdNfRs7lkPq4g4Q/arcgis/rest/services/Envr_admin_FFS_danger_public/FeatureServer/2",),
    reason="drawn from njgin/'s resources, extracted once there (decision 34); checked names the layers this org's data arrives in; the org's own non-ArcGIS sources are listed in the docstring, still to wire",
)
