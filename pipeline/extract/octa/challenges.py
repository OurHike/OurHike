"""Oregon-California Trails Association: challenges, published, and not landed (coverage audit
2026-10-01, batch c11_nht).

NPS Passport stamps fit #1780: Let a club publish a challenge — places on its own trails that hikers
opt into and tag at camp's "places you opt into" shape

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`NPSAPI/passportstamplocations` oreg 21, cali 18. NTIR POIs carry `passport=1` (217 across all NTIR "
        "trails) with `pptext`",
    ),
    where=(
        "https://mapservices.nps.gov/arcgis/rest/services",
        "https://octa-trails.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
