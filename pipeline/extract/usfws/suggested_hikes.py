"""US Fish & Wildlife Service: suggested hikes, published, and not landed (coverage audit 2026-10-01,
batch c9_federal_state_rest).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Per-refuge `…/visit-us/trails` pages, e.g. `https://www.fws.gov/refuge/blackwater/visit-us/trails` and"
        " `…/willapa/visit-us/trails`. The `Trails_Info` table (2,982 rows) is the structured side.",
    ),
    where=(
        "https://www.fws.gov/refuge/blackwater/visit-us/trails",
        "https://fws.gov/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
