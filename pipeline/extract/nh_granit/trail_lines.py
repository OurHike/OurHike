"""NH GRANIT (University of New Hampshire): trail lines, published, and not landed (coverage audit
2026-10-01, batch c9_federal_state_rest).

Retired, not recommended. Listed as available only because the definition requires it.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`nhgeodata.unh.edu/nhgeodata/rest/services/CSD/RecreationResources/MapServer/2`: 15,791 lines, "
        "matching #1711's 2026-09-26 count. The catalogue's 19,877 was counted 2026-09-17, before the republish"
        " #1646 — NH GRANIT trails in cell n44w072 went from 2,278 to 3,685 miles between UA builds "
        "2026-09-21-2 and 2026-09-23-4, and nothing says why describes. The layer's description today: "
        '"extracted from USGS Digital Line Graph data".',
    ),
    where=("https://nhgeodata.unh.edu/nhgeodata/rest/services/CSD/RecreationResources/MapServer/2",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
