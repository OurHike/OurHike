"""Colorado Mountain Club: challenges, the summit completer programme, whose page carries no peak list, and
not landed (decision 54 wave 5, section K, 2026-10-04).

/community/summit-completers names the 54 14ers the club recognises in a sentence and links its full list of 14er
completers, a roster, never read; the peak list itself, and the 13er, Centennial and Bicentennial lists, are not on
the page.

The note this replaces read, whole:

Colorado Mountain Club: challenges, published, and not landed (coverage audit 2026-10-01, batch
c5_regional_2).

The page defines each list in prose; I saw no table of peaks with coordinates. The terms block it.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): `/community/summit-completers`. CMC's official 14er list is 54
peaks: 52 named summits over 14,000 ft with more than 300 ft prominence, plus North Maroon and El
Diente, excluding Challenger Point. It also keeps 13er, Centennial and Bicentennial lists, and a
completer form. Records go back to 1911 (HTML page).

Its `where`: https://cmc.org/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "https://www.cmc.org/community/summit-completers (HTTP 200, 45,119 bytes, 2026-10-04): 'The CMC officially recognizes 54 14ers', a link to the completers' spreadsheet",
    ),
    where=("https://www.cmc.org/community/summit-completers",),
    reason="not published as a list: the page names no peak, and its completers' list is a roster",
)
