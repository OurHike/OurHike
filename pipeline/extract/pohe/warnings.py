"""Potomac Heritage Trail Association: warnings, drawn from nps/warnings.py's NPS alerts resource
(decision 53, phase B, 2026-10-03).

NPS's alerts for park code `pohe` land once, in nps/warnings.py's `nps_alerts`, whose sources.json
entry lists it against this folder in `park_codes` (decision 34). NPS's Danger, Caution and
Information categories are the warnings half, split from the rest in dbt.

The coverage audit's note, kept as it was (restated from reference/org_coverage.json, whose text is
trimmed where it ends in '…'):

Lives in the `nps` folder, like `natr`'s warnings row.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 3),
    checked=(
        (
            "NPS alerts API, `parkCode=pohe` (the decision 53 inventory, batch 5, 2026-10-03): 0 alerts. Landed "
            "by nps/warnings.py as nps_alerts."
        ),
        (
            "(coverage audit, 2026-10-01) NPS alerts API `parkCode=pohe`, categories Caution and Danger: 0 today. "
            "The association publishes none. NVRC's `PHNST_Wayfinding_Amenities_Assessment` records sign "
            "`Condition` and `Issue`. That is an asset inventory, not a hazard notice, so it is not a warnings "
            "source."
        ),
    ),
    where=(
        "https://developer.nps.gov/api/v1/alerts?parkCode=pohe",
        "https://mapservices.nps.gov/arcgis/rest/services",
        "https://nps.gov/pohe/",
    ),
    reason=(
        "drawn from nps/'s resources, extracted once there (decision 34); checked names the layer this org's data arrives in"
    ),
)
