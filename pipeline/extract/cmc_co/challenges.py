"""Colorado Mountain Club: challenges, published, and not landed (coverage audit 2026-10-01, batch
c5_regional_2).

The page defines each list in prose; I saw no table of peaks with coordinates. The terms block it.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`/community/summit-completers`. CMC's official 14er list is 54 peaks: 52 named summits over 14,000 ft "
        "with more than 300 ft prominence, plus North Maroon and El Diente, excluding Challenger Point. It also"
        " keeps 13er, Centennial and Bicentennial lists, and a completer form. Records go back to 1911 (HTML "
        "page).",
    ),
    where=("https://cmc.org/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
