"""Natchez Trace NST (NPS-administered): warnings, drawn from nps/warnings.py's NPS alerts resource
(decision 53, phase B, 2026-10-03).

NPS's alerts for park code `natr` land once, in nps/warnings.py's `nps_alerts`, whose sources.json
entry lists it against this folder in `park_codes` (decision 34). NPS's Danger, Caution and
Information categories are the warnings half, split from the rest in dbt.

The inventory also found a web page for this club, which other phase B readers take; if one lands
for this type it takes this file, and this note becomes a line in its docstring.

The coverage audit's note, kept as it was (restated from reference/org_coverage.json, whose text is
trimmed where it ends in '…'):

The endpoint exists and may be empty, which decision 14 allows for warnings. Skeptic spot-check: 0
confirmed.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 3),
    checked=(
        (
            "NPS alerts API, `parkCode=natr` (the decision 53 inventory, batch 4, 2026-10-03): 1: 'Current Park "
            "Closures' (category Park Closure, lastIndexedDate 2026-08-03), a pointer to the road-and-site-status "
            "page; Caution/Danger 0. Landed by nps/warnings.py as nps_alerts."
        ),
        "(coverage audit, 2026-10-01) The NPS alerts API Caution and Danger categories: 0 for `natr` today.",
    ),
    where=(
        "https://developer.nps.gov/api/v1/alerts?parkCode=natr",
        "https://mapservices.nps.gov/arcgis/rest/services",
        "https://nps.gov/natr/",
    ),
    reason=(
        "drawn from nps/'s resources, extracted once there (decision 34); checked names the layer this org's data arrives in"
    ),
)
