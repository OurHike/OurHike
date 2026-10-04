"""Forest Park Conservancy: challenges, a fundraising run, and not landed (decision 54 wave 5, section K,
2026-10-04).

The Nasty Challenge: five routes in Forest Park and Marquam, run or hiked, raising money on causevox.com ('$7,471.26
raised' in 2024). A fundraiser's routes on another site are not a club's list of places.

The note this replaces read, whole:

Forest Park Conservancy: challenges, published, and not landed (coverage audit 2026-10-01, batch
c6_regional_3).

A fundraiser with a route list. The routes themselves are the partner club's. Skeptic (Measured from
FPC's own site, 2026-10-01): "Nasty Challenge 2025 Wrap-Up: The Biggest Nasty Challenge to Date" (posted
2026-03-16) reports "five nasty routes" over five months. Over 200 hikers and runners took …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): The Nasty Challenge, in the nav and linked to
`https://the-nasty-challenge-2025.causevox.com/`. Five routes (North, South, Alphabet, Flaming, Skyline)
in Forest Park and Marquam, run or hiked, with NW Dirt Churners. The 2024 wrap-up reports $7,471.26
raised.

Its `where`: https://the-nasty-challenge-2025.causevox.com/
https://forestparkconservancy.org/nasty-challenge-2024-wrap-up/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "(the coverage audit, 2026-10-01) https://the-nasty-challenge-2025.causevox.com/",
        "no request sent today: the coverage audit's reading, 2026-10-01",
    ),
    where=("https://the-nasty-challenge-2025.causevox.com/",),
    reason="not this type: a fundraising event on another site",
)
