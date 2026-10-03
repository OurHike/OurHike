"""Rocky Mountain Field Institute: suggested hikes, nothing published (coverage audit 2026-10-01, batch
c5_regional_2).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'Same pages. (Skeptic: the nearest thing is one blog post, "Trail Gold: Local Fall Color Adventures" '
        "(2025-09-03), where staff name favourite leaf-peeping spots such as Gold Camp Road and Mueller State "
        "Park. It describes no routes, so the verdict stands.)",
    ),
    where=("https://rmfi.org/",),
)
