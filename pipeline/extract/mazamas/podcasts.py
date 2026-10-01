"""Mazamas: podcasts, nothing published (coverage audit 2026-10-01, batch c6_regional_3).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "The sitemap has no podcast URL. `/publications/` lists the Mazama magazine and annuals only.",
        'Skeptic: the Apple directory for "Mazamas" has 1 result, "What Happened in Skinner" by "Mazama '
        'Entertainment", which is unrelated. The site is not WordPress (`/feed/` answers 404).',
    ),
    where=("https://mazamas.org/",),
)
