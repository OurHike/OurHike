"""Star-Spangled Banner NHT (NPS): warnings, drawn from nps/warnings.py's NPS alerts resource (decision
53, phase B, 2026-10-03).

NPS's alerts for park code `stsp` land once, in nps/warnings.py's `nps_alerts`, whose sources.json
entry lists it against this folder in `park_codes` (decision 34). NPS's Danger, Caution and
Information categories are the warnings half, split from the rest in dbt.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 3),
    checked=(
        (
            "NPS alerts API, `parkCode=stsp` (the decision 53 inventory, batch 5, 2026-10-03): 1 alerts. Landed "
            "by nps/warnings.py as nps_alerts."
        ),
        "(coverage audit, 2026-10-01) Same endpoint, 0 Danger/Caution today",
    ),
    where=(
        "https://developer.nps.gov/api/v1/alerts?parkCode=stsp",
        "https://mapservices.nps.gov/arcgis/rest/services",
        "https://nps.gov/stsp/",
    ),
    reason=(
        "drawn from nps/'s resources, extracted once there (decision 34); checked names the layer this org's data arrives in"
    ),
)
