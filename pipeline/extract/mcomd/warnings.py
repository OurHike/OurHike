"""Mountain Club of Maryland: warnings, published, and not landed (coverage audit 2026-10-01, batch
c2_at_clubs_mid).

Seasonal and evergreen rather than live.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'Same API: hunting-season posts 2022-10-28 ("It\'s the Season for Orange") and 2023-09-23; '
        "bear-container policy post 2022-07-15",
    ),
    where=(
        "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services",
        "https://services9.arcgis.com/Nb3RpWJ36xRlYQj2/arcgis/rest/services",
        "https://mcomd.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
