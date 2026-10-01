"""Cumberland Trail / Tennessee State Parks: places, published, and not landed (coverage audit
2026-10-01, batch c9_federal_state_rest).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`.../State_Park_Boundaries_Primary_March_2024_view2/FeatureServer/331`: 68 polygons. CTSST "
        "`PUBLIC_Properties_2020` (0): 39 polygons, edited 2026-04-02. JSON:API `node--parks`.",
    ),
    where=("https://tnstateparks.com/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
