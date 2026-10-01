"""Natchez Trace NST (NPS-administered): trail lines, drawn from another folder's resource (coverage
audit 2026-10-01, batch c10_nst_rest).

`nps_trails` is registered but not yet reaching hikers (#1787 — The seventeen organizations reach no
hiker after all…).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Arrives via `nps` as `nps_trails`: `UNITCODE='NATR'` 111 features, including the NST sections (\"NST - "
        'Highland Rim Section" 4, "NST - Yockanookany Section", "NST - Blackland Prairie Section", "RI/PG/TU '
        'National Scenic Trail", "NA National Scenic Trail (Potkopinu)").',
    ),
    where=(
        "https://mapservices.nps.gov/arcgis/rest/services",
        "https://nps.gov/natr/",
    ),
    reason="drawn from nps/'s resources, extracted once there (decision 34); checked names the layer this org's data arrives in",
)
