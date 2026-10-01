"""Pacific Northwest Trail Association: podcasts, nothing published (coverage audit 2026-10-01, batch
c10_nst_rest).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Web search: third-party shows only (Cascade Hiker; Explore the PNW).",
        "Skeptic: none of the 32 WordPress categories is a podcast category. WP REST `search=podcast` returns 2"
        " unrelated hits (Project Thunderbird, 2018 Bellingham Ruck). The 188-URL sitemap has no audio page. "
        'iTunes "Pacific Northwest Trail Association" finds no PNTA show.',
    ),
    where=("https://pnt.org/",),
)
