"""Natural Bridge Appalachian Trail Club: warnings, published, and not landed (coverage audit
2026-10-01, batch c2_at_clubs_mid).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "The same endpoint: one feed split by `obstructs_trail` (decision 7). `/pdfs/SAFETY.pdf` is static. The"
        " RIMS digests on TATC's site also cover this section",
    ),
    where=("https://nbatc.org/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
