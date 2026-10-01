"""Rocky Mountain Field Institute: challenges, nothing published (coverage audit 2026-10-01, batch
c5_regional_2).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Same pages. (Skeptic: `/awards` lists awards RMFI has received, such as the 2021 USFS Chief's Honor "
        "Award, not awards it gives hikers.)",
    ),
    where=("https://rmfi.org/",),
)
