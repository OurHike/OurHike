"""Continental Divide Trail Society: suggested hikes, published, and not landed (coverage audit
2026-10-01, batch c10_nst_rest).

Paper only, copyrighted, sold second-hand. Not a load candidate. Recorded so nobody re-finds it and
counts it as data.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'The "Wolf Guides", Guide to the Continental Divide Trail: Vol. 3 Wyoming (1980), Southern Colorado '
        "(1986). Found as Amazon and eBay listings in a web search.",
    ),
    where=("https://cdtsociety.org/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
