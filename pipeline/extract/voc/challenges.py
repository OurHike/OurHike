"""Volunteers for Outdoor Colorado: challenges, nothing published (coverage audit 2026-10-01, batch
c5_regional_2).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'Same. (Skeptic: the 11 "award" URLs in the sitemap are VOC\'s volunteer recognition nights, a '
        "scholarship, and awards or grants VOC itself received.)",
    ),
    where=("https://voc.org/",),
)
