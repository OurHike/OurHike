"""Pinhoti Trail Alliance: suggested hikes, could not be told (coverage audit 2026-10-01, batch
c7_regional_4).

The PTA's old section guides are gone with the domain. Skeptic: GPTA's 2021 Georgia guide survives
as a mileage summary on `pinhotiexperience.org/section-13-1`, and its PDF link is dead (404). That
belongs to the proposed GPTA and PinX rows, not to the PTA.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=("Same.",),
    where=("https://pinhotiexperience.org/section-13-1",),
    reason="the coverage audit could not tell on 2026-10-01; checked says what stopped it",
)
