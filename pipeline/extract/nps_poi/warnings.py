"""National Park Service: warnings, published, and not landed (coverage audit 2026-10-01, batch
c9_federal_state_rest).

That Danger example is a closure filed under Danger. The category is not a reliable closure/warning
split on its own.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'Same endpoint: the `Danger` and `Caution` categories (23 of 100 sampled). Example: "South Pasture '
        'Trail, all River Access Closed Due to Flood Conditions" (Danger).',
    ),
    where=("https://nps.gov/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
