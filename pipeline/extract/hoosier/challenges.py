"""Hoosier Hikers Council: challenges, published, and not landed (coverage audit 2026-10-01, batch
c5_regional_2).

It ended in 2016, so the challenges mart should probably leave it out. Recorded so nobody hunts for
it again. (Skeptic correction, 2026-10-01: `/bicentennial-challenge/` says "The time period for the
challenge was from January 1, 2016 through December 31, 2017", so it ended at the close of 2017 …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=('"2016 Bicentennial Challenge": hike 200 mi of Indiana natural-surface trail. The list is the PDF above.',),
    where=("https://hoosierhikerscouncil.org/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
