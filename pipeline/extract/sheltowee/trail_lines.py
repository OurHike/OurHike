"""Sheltowee Trace Association: trail lines, drawn from another folder's resource (coverage audit
2026-10-01, batch c8_regional_5).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Via `usfs` → `usfs_trails`: 87 features, 290.22 mi, every one `terra_motorized='N/A'` and so kept "
        "under #1711's rule (#1711 — Ship only hiking trails: remove NH GRANIT, and drop USFS motorized trails "
        "nationwide). Main segments: `SHELTOWEE TRACE` 080211, 21 / 109.22 mi; 080214, 38 / 109.57 mi; 080216, "
        "5 / 67.89 mi. Also `FLOOD ROUTE FOR SHELTOWEE LON` (14 / 2.91 mi) and connectors and spurs. "
        "`nps_trails`: 11 BISO features. Own geometry: none (correction 3).",
    ),
    where=(
        "https://apps.fs.usda.gov/arcx/rest/services",
        "https://sheltoweetrace.org/",
    ),
    reason="drawn from usfs/'s resources, extracted once there (decision 34); checked names the layer this org's data arrives in",
)
