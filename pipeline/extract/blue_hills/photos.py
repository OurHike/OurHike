"""Friends of the Blue Hills: photos, nothing published (coverage audit 2026-10-01, batch
c4_regional_1).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=("The 2026 photo contest's entries are not openly licensed. A Flickr link exists; its licence was not checked.",),
    where=(
        "https://arcgisserver.digital.mass.gov/arcgisserver/rest/services",
        "https://services1.arcgis.com/7iJyYTjCtKsZS1LR/arcgis/rest/services",
        "https://friendsofthebluehills.org/",
    ),
)
