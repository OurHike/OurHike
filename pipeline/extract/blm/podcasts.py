"""Bureau of Land Management: podcasts, published, and not landed (coverage audit 2026-10-01, batch
b6_federal).

Programming, not trail audio.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        '"On the Ground": `https://www.blm.gov/media/podcasts/otg.rss`, 26 items with enclosures, newest '
        "2025-09-24. Also Alaska Frontiers and Your American Lands (`blm.gov/media/podcasts/…`, search).",
    ),
    where=(
        "https://www.blm.gov/media/podcasts/otg.rss",
        "https://blm.gov/media/podcasts/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
