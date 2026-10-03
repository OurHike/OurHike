"""Pacific Northwest Trail Association: warnings, published, and not landed (coverage audit 2026-10-01,
batch c10_nst_rest).

The conditions page is 14 months stale. Carry its own date and never render it as current. Skeptic
spot-check: the page still reads "Last Updated: August 1, 2025" today.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        '`/trail-conditions/` page, "Last Updated: August 1, 2025". Static pages `/bears/`, '
        "`/challenges-and-risks/` and `/snow/`.",
    ),
    where=("https://pnt.org/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
