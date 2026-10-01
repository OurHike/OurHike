"""Green Mountain Club: photos, published, and not landed (coverage audit 2026-10-01, batch
c1_at_clubs_north).

Not openly licensed. Publishing these needs a basis the maintainer records, the same way
`photo_licence` does for ATC's.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`OS_MASTER.Photo1` holds URLs on 59 of 72 sites, hosted in the S3 bucket `gmc-public-web-map`. No "
        "licence is stated. LOADED via atc: `Photo1` on 27 of 27 GMC shelters.",
    ),
    where=(
        "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services",
        "https://services8.arcgis.com/kClE0vHJkIEmhQ53/arcgis/rest/services",
        "https://services9.arcgis.com/Nb3RpWJ36xRlYQj2/arcgis/rest/services",
        "https://greenmountainclub.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
