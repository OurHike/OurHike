"""The Cohos Trail Association: points of interest, published, and not landed (coverage audit
2026-10-01, batch c4_regional_1).

Page only. The Baldhead Shelter was removed in 2025 (from `/trail-changes-and-updates/`).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`/places-to-stay/` names 8 shelters, cabins and huts, south to north, with no coordinates. Also `/supply-chache/`.",
    ),
    where=("https://cohostrail.org/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
