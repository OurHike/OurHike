"""Connecticut Forest & Park Association: warnings, published, and not landed (coverage audit
2026-10-01, batch c10_nst_rest).

The "CLEARED" items are reopenings and must not render as hazards.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'Non-closure items in the same feed: "Nipmuck Trail Parallel to Chaffeville Rd – Caution" (2025-05-06),'
        ' "North Stonington – Difficult/Unblazed Trail Section" (2025-01-06), "Ragged Mountain Preserve, Storm '
        'Damage CLEARED" (2026-07-17).',
    ),
    where=(
        "https://services1.arcgis.com/FjPcSmEFuDYlIdKC/arcgis/rest/services",
        "https://ctwoodlands.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
