"""Wasatch Mountain Club: challenges, nothing published (coverage audit 2026-10-01, batch
c5_regional_2).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Its awards are service awards (Alexis Kelner Conservation, Pa Parry, Lifetime Achievement). (Skeptic: "
        'the sitemap\'s only "award" URLs are those three pages and '
        '`history-maker-award-video-of-wmc-history.mp4`. The "Wasatch 7 Peak Challenge" on peakery.com and the '
        "\"Wasatch 11,000 foot peaks\" list on SummitPost are third parties' lists, not WMC's.)",
    ),
    where=("https://peakery.com",),
)
