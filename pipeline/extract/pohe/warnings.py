"""Potomac Heritage Trail Association: warnings, published, and not landed (coverage audit 2026-10-01,
batch c10_nst_rest).

Lives in the `nps` folder, like `natr`'s warnings row.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "NPS alerts API `parkCode=pohe`, categories Caution and Danger: 0 today. The association publishes "
        "none. NVRC's `PHNST_Wayfinding_Amenities_Assessment` records sign `Condition` and `Issue`. That is an "
        "asset inventory, not a hazard notice, so it is not a warnings source.",
    ),
    where=(
        "https://mapservices.nps.gov/arcgis/rest/services",
        "https://nps.gov/pohe/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
