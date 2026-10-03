"""Forest Park Conservancy: challenges, published, and not landed (coverage audit 2026-10-01, batch
c6_regional_3).

A fundraiser with a route list. The routes themselves are the partner club's. Skeptic (Measured from
FPC's own site, 2026-10-01): "Nasty Challenge 2025 Wrap-Up: The Biggest Nasty Challenge to Date"
(posted 2026-03-16) reports "five nasty routes" over five months. Over 200 hikers and runners took …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "The Nasty Challenge, in the nav and linked to `https://the-nasty-challenge-2025.causevox.com/`. Five "
        "routes (North, South, Alphabet, Flaming, Skyline) in Forest Park and Marquam, run or hiked, with NW "
        "Dirt Churners. The 2024 wrap-up reports $7,471.26 raised.",
    ),
    where=(
        "https://the-nasty-challenge-2025.causevox.com/",
        "https://forestparkconservancy.org/nasty-challenge-2024-wrap-up/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
