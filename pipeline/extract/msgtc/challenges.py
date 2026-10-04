"""Monadnock-Sunapee Greenway Trail Club: challenges, a patch for sale, and not landed (decision 54 wave 5,
section K, 2026-10-04).

The store sells an 'END to END' rocker patch for $5; no challenge's rules or places are published.

The note this replaces read, whole:

Monadnock-Sunapee Greenway Trail Club: challenges, published, and not landed (coverage audit 2026-10-01,
batch c4_regional_1).

Thin: a patch, no application.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): `/store/`: an "END to END" rocker patch, $5.

Its `where`: https://msgtc.org/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "(the coverage audit, 2026-10-01) /store/: an 'END to END' rocker patch, $5",
        "no request sent today: the coverage audit's reading, 2026-10-01",
    ),
    where=("https://msgtc.org/store/",),
    reason="not this type: a patch for sale, no list of places",
)
