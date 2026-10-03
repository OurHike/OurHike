"""E Mau Na Ala Hele: warnings, drawn from nps/warnings.py's NPS alerts resource (decision 53, phase B,
2026-10-03).

NPS's alerts for park code `alka` land once, in nps/warnings.py's `nps_alerts`, whose sources.json
entry lists it against this folder in `park_codes` (decision 34). NPS's Danger, Caution and
Information categories are the warnings half, split from the rest in dbt.

The inventory also found a web page for this club, which other phase B readers take; if one lands
for this type it takes this file, and this note becomes a line in its docstring.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 3),
    checked=(
        (
            "NPS alerts API, `parkCode=alka` (the decision 53 inventory, batch 2, 2026-10-03): 0 alerts. Same "
            "parkCode (alka) as ala-kahakai: one row serves both, deduped in dbt. Landed by nps/warnings.py as "
            "nps_alerts."
        ),
        "(coverage audit, 2026-10-01) Same",
    ),
    where=(
        "https://developer.nps.gov/api/v1/alerts?parkCode=alka",
        "https://mapservices.nps.gov/arcgis/rest/services",
        "https://emaunaalahele.org/",
    ),
    reason=(
        "drawn from nps/'s resources, extracted once there (decision 34); checked names the layer this org's data arrives in"
    ),
)
