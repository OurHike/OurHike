"""Mohonk Preserve: photos, nothing published (coverage audit 2026-10-01, batch b4_oprhp_mohonk_gatc).

Nothing openly licensed. Wikimedia Commons (`_shared/`) is the path.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'The site footer reads "© 2026 Mohonk Preserve". The WP media library has 3,408 items, with '
        'photographer credits in page text ("Banner photo … by a named individual"). `/photo-gallery/` is a '
        "commercial film-location page. `hasAttachments` is false on the trails and boundary layers.",
    ),
    where=(
        "https://mohonkpreserve.org/",
        "https://services8.arcgis.com/cQ05sucxF4UWabFF/arcgis/rest/services",
    ),
)
