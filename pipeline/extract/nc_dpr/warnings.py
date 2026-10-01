"""NC Division of Parks & Recreation — NC Trails: warnings, published, and not landed (coverage audit
2026-10-01, batch c9_federal_state_rest).

Banners mix closure and warning text, so they need the decision-7 classifier.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=('Same banners. Example: "There are no gas stations between Asheville & the park."',),
    where=(
        "https://services.nconemap.gov/secure/rest/services",
        "https://services7.arcgis.com/SEKZuPu27jfvDQ5b/arcgis/rest/services",
        "https://trails.nc.gov/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
