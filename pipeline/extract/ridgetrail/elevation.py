"""Bay Area Ridge Trail Council: elevation, nothing published (coverage audit 2026-10-01, batch
c6_regional_3).

These are attributes of sections, carried with suggested_hikes. USGS 3DEP for data.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'The Planning Navigator has an "Elevation Gain/Loss" text column per section (e.g. "190\'/120\'"). The '
        "route layer has `Highest_Elevation`, and its `ElevationGainLoss` field is null.",
    ),
    where=(
        "https://services5.arcgis.com/6iLCtMhqIxD1wlgk/arcgis/rest/services",
        "https://ridgetrail.org/",
    ),
)
