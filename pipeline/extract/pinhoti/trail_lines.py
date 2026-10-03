"""Pinhoti Trail Alliance: trail lines, drawn from another folder's resource (coverage audit
2026-10-01, batch c7_regional_4).

The trail is 339 mi. State, private and road-walk miles are not in the layer.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "21 features, 231.7 mi:",
        "`PINHOTI` on Chattahoochee-Oconee (0803): 100.2 mi",
        "`PINHOTI NRT…` on National Forests in Alabama (0801): 131.5 mi",
    ),
    where=(
        "https://apps.fs.usda.gov/arcx/rest/services",
        "https://conservationgis.alabama.gov/adcnrweb/rest/services",
        "https://pinhotitrailalliance.org/",
    ),
    reason="drawn from usfs/'s resources, extracted once there (decision 34); checked names the layer this org's data arrives in",
)
