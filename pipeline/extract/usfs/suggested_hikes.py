"""USDA Forest Service: suggested hikes, published, and not landed (coverage audit 2026-10-01, batch
b6_federal).

`activitydescription` read "None" on the one row sampled, so how much text is actually present is
Unvalidated. The service description says these come from the Recreation Portal that feeds
recreation.gov.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`.../EDW/EDW_RecreationAreaActivities_01/MapServer/0` (point, 52,482 rows; Day Hiking 6,523, "
        "Backpacking 2,755; fields `activitydescription`, `recareadescription`, `recareaurl`, `openstatus`). "
        '`EDW_RecreationOpportunities_01` "Day Hiking" markers: 923. Pages: '
        "`fs.usda.gov/r08/northcarolina/recreation/opportunities/hiking` and the like (search).",
    ),
    where=(
        "https://fs.usda.gov/r08/northcarolina/recreation/opportunities/hiking",
        "https://recreation.gov",
        "https://apps.fs.usda.gov/arcx/rest/services",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
