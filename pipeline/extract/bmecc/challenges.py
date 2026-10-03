"""Blue Mountain Eagle Climbing Club: challenges, nothing published (coverage audit 2026-10-01, batch
c2_at_clubs_mid).

The homepage's "patches" are merchandise in the store (`bmecc.square.site`), not an award.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=("Checked: nav, homepage, all A.T. pages",),
    where=(
        "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services",
        "https://services9.arcgis.com/Nb3RpWJ36xRlYQj2/arcgis/rest/services",
        "https://bmecc.org/",
    ),
)
