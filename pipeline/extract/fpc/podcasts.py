"""Forest Park Conservancy: podcasts, nothing published (coverage audit 2026-10-01, batch
c6_regional_3).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Nav and sitemap.",
        'Skeptic: the category `audio` exists with 0 posts. The Apple directory for "Forest Park Conservancy" '
        "returns 8 shows, none of them FPC's.",
    ),
    where=(
        "https://www.portlandmaps.com/od/rest/services",
        "https://forestparkconservancy.org/",
    ),
)
