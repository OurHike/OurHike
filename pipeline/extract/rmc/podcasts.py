"""Randolph Mountain Club: podcasts, nothing published (coverage audit 2026-10-01, batch
c1_at_clubs_north).

—

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Nav and the WP page list.",
        'Skeptic, 2026-10-01: a web search finds RMC\'s "Tales from the Trails" (2021), a video series on '
        "YouTube, and RMC caretakers as guests on a third party's show.",
    ),
    where=(
        "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services",
        "https://services9.arcgis.com/Nb3RpWJ36xRlYQj2/arcgis/rest/services",
        "https://randolphmountainclub.org/",
    ),
)
