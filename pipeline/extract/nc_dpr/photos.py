"""NC Division of Parks & Recreation — NC Trails: photos, nothing published (coverage audit 2026-10-01,
batch c9_federal_state_rest).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "The homepage links only Instagram, Facebook and YouTube. DPR's `Photos_let` service is an 8-point map "
        "tour with no licence stated.",
    ),
    where=(
        "https://services.nconemap.gov/secure/rest/services",
        "https://services7.arcgis.com/SEKZuPu27jfvDQ5b/arcgis/rest/services",
        "https://trails.nc.gov/",
    ),
)
