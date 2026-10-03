"""Foothills Trail Conservancy: points of interest, published, and not landed (coverage audit
2026-10-01, batch c5_regional_2).

The FAQ says campsites, bear cables and water posts (marked by "a wooden post with a blue
reflector") are listed only in the paid guidebook and FarOut.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`/maps-coordinates-2/`: 17 access points (trailheads, parking, boat access) in "
        "degrees-decimal-minutes, in an HTML table. (Skeptic spot-check, 2026-10-01: 17 rows again, from "
        '"Oconee St Park Access 34 51.807 / 83 05.880" to "Caesar\'s Head St Park Access".)',
    ),
    where=("https://foothillstrail.org/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
