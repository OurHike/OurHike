"""Superior Hiking Trail Association: challenges, published, and not landed (coverage audit 2026-10-01,
batch c7_regional_4).

Pages.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        '`/hike50challenge/`: an annual patch. The page text reads "Hike any 40 miles of the Superior Hiking '
        'Trail to earn your annual … patch". `/end-2-ender-program/`: certificate, patch and magnet, on the '
        "honour system, for members at $45/yr or more or recent volunteers.",
    ),
    where=("https://superiorhiking.org/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
