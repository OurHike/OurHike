"""Oregon Natural Desert Association: trail lines, published, and not landed (coverage audit
2026-10-01, batch c7_regional_4).

Restricted. Not fetched. Whether a state copy may be used is the maintainer's call (terms section).
ONDA's ArcGIS account (a personal ArcGIS account) has StoryMaps only.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "GPX, behind the waiver form `https://www.tfaforms.com/4757425` (from "
        "`/regions/oregon-desert-trail/plan-a-trip/`). Separately, the `orstateparks` GeoJSON item "
        "`c851af0d384a4dfc9cf470993339a81c` (30,404 B, 2024-04-30, no licence).",
    ),
    where=(
        "https://www.tfaforms.com/4757425",
        "https://onda.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
