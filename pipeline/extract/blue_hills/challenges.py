"""Friends of the Blue Hills: challenges, published, and not landed (coverage audit 2026-10-01, batch
c4_regional_1).

A page.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        '`/125mileclub/`: "hike every mile of every trail". The Skyline Trail earns a first patch, all 125 '
        "miles a second, a repeat a third.",
    ),
    where=(
        "https://arcgisserver.digital.mass.gov/arcgisserver/rest/services",
        "https://services1.arcgis.com/7iJyYTjCtKsZS1LR/arcgis/rest/services",
        "https://friendsofthebluehills.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
