"""Monadnock-Sunapee Greenway Trail Club: closures, published, and not landed (coverage audit
2026-10-01, batch c4_regional_1).

A page.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        '`/trail-conditions/`: dated entries (April 2026, "entire 48.7 miles … swept, cleared"), plus a '
        'relocation notice in Stoddard with a "Download Relocation Map" link.',
    ),
    where=("https://msgtc.org/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
