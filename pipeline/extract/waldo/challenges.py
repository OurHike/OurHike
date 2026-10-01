"""Waldo County Trails Coalition: challenges, nothing published (coverage audit 2026-10-01, batch
c4_regional_1).

Skeptic re-checked 2026-10-01: the same 68 URLs and the same five pages scanned for challenge,
passport, end-to-end, patch and badge text. The only hit is `/activities` on running the whole trail
("timing… synchronized with the times that the entire trail is open"). That is advice, not a
programme. …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=("No completion programme in the nav.",),
    where=(
        "https://www.hillstosea.org/maps",
        "https://www.hillstosea.org/closures",
    ),
)
