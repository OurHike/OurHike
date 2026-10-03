"""AMC Berkshire Chapter: challenges, published, and not landed (coverage audit 2026-10-01, batch
c1_at_clubs_north).

It expires in 30 days and is activity-based, not place-based. Probably out of #1780's shape
(Reasoned).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        '`/150-anniversary-challenge.cgi` (page): 150 "miles worth" of activities between 2026-01-01 and '
        "2026-10-31, earning a patch. Registration is by email.",
    ),
    where=(
        "https://services1.arcgis.com/7iJyYTjCtKsZS1LR/arcgis/rest/services",
        "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services",
        "https://services9.arcgis.com/Nb3RpWJ36xRlYQj2/arcgis/rest/services",
        "https://amcberkshire.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
