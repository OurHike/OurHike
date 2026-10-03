"""MassGIS (Bureau of Geographic Information): suggested hikes, nothing published (coverage audit
2026-10-01, batch b5_nyc_nj_ct_ma_pa).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=("Same listing.",),
    where=(
        "https://arcgisserver.digital.mass.gov/arcgisserver/rest/services",
        "https://mass.gov/massgis/",
    ),
)
