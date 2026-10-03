"""Old Spanish Trail Association: warnings, drawn from nps/warnings.py's NPS alerts resource (decision
53, phase B, 2026-10-03).

NPS's alerts for park code `olsp` land once, in nps/warnings.py's `nps_alerts`, whose sources.json
entry lists it against this folder in `park_codes` (decision 34). NPS's Danger, Caution and
Information categories are the warnings half, split from the rest in dbt.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 3),
    checked=(
        (
            "NPS alerts API, `parkCode=olsp` (the decision 53 inventory, batch 4, 2026-10-03): 0 alerts for olsp; "
            "the conditions page (www.nps.gov/olsp/planyourvisit/conditions.htm, 200) holds navigation only, "
            "'Last updated: April 23, 2025'. Landed by nps/warnings.py as nps_alerts."
        ),
        "(coverage audit, 2026-10-01) Same",
    ),
    where=(
        "https://developer.nps.gov/api/v1/alerts?parkCode=olsp",
        "https://mapservices.nps.gov/arcgis/rest/services",
        "https://oldspanishtrail.org/",
    ),
    reason=(
        "drawn from nps/'s resources, extracted once there (decision 34); checked names the layer this org's data arrives in"
    ),
)
