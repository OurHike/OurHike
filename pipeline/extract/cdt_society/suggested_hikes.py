"""Continental Divide Trail Society: suggested hikes, published only as books for sale (decision 54 wave 5,
section K, 2026-10-04).

The Society's 'Wolf Guides' (Guide to the Continental Divide Trail, Vol. 3 Wyoming 1980, Southern Colorado 1986)
are printed books, found as resale listings (the coverage audit); nothing of them is online to read. No request
sent today.

The note this replaces read, whole:

Continental Divide Trail Society: suggested hikes, published, and not landed (coverage audit 2026-10-01,
batch c10_nst_rest).

Paper only, copyrighted, sold second-hand. Not a load candidate. Recorded so nobody re-finds it and
counts it as data.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): The "Wolf Guides", Guide to the Continental Divide Trail: Vol. 3
Wyoming (1980), Southern Colorado (1986). Found as Amazon and eBay listings in a web search.

Its `where`: https://cdtsociety.org/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "(the coverage audit, 2026-10-01) the Wolf Guides, Vol. 3 Wyoming (1980) and Southern Colorado (1986), as Amazon and eBay listings",
    ),
    where=("https://cdtsociety.org/",),
    reason="not published online: printed guidebooks",
)
