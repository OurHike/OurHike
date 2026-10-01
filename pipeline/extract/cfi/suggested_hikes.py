"""Colorado Fourteeners Initiative: suggested hikes, published, and not landed (coverage audit
2026-10-01, batch c5_regional_2).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'The 53 peak pages each have a "Recommended Route" and route narrative (pages, 2012–2017). '
        "`/wp-content/uploads/2019-14er-Report-Card-Combined-Final-Document.pdf` grades 56 routes (PDF).",
    ),
    where=("https://14ers.org/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
