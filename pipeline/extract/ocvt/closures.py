"""Outdoor Club at Virginia Tech: closures, published, and not landed (coverage audit 2026-10-01, batch
c3_at_clubs_south).

Dormant: newest closure post is 2022-01-14, and both relay ATC/RATC notices. Historical value only.
The extractor would be a page scrape of `/news/<N>`; the note should say "published, last item
2022-01".

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`https://ocvt.club/news/archive` (page, HTML only; no feed, no sitemap) lists 97 items. Two are trail "
        'closures: `https://ocvt.club/news/73` "Peters Mountain Trail Closure due to Ice Damage" (2021-02-26: '
        '"The damaged towers create a significant safety risk to visitors and the Trail will remain closed '
        'until the area can be made safe") and `https://ocvt.club/news/84` "McAfee Knob fire road closed" '
        '(2022-01-14: "closed to all hikers from January 17, 2022 to February 11"). Also "McAfee\'s Knob '
        "Parking\" (2021-10-22). ATC has 0 rows on OCVT's segments.",
    ),
    where=(
        "https://ocvt.club/news/archive",
        "https://ocvt.club/news/73",
        "https://ocvt.club/news/84",
        "https://outdoor.org.vt.edu/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
