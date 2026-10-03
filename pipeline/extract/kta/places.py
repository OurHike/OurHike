"""Keystone Trails Association: places, published, and not landed (coverage audit 2026-10-01, batch
c1_at_clubs_north).

Prose pages; no coordinates seen.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        '"Find a Trail": 28 trail pages in the sitemap (`-trail.html` / `trail-system.html`). For example, '
        '`quehanna-trail.html` gives "73.7-mile … loop", "main trailhead is at Parker Dam State Park". Also '
        "`hiking-clubs.html` (club directory).",
    ),
    where=(
        "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services",
        "https://services9.arcgis.com/Nb3RpWJ36xRlYQj2/arcgis/rest/services",
        "https://kta-hike.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
