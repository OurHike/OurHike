"""Oregon-California Trails Association: warnings, drawn from nps/warnings.py's NPS alerts resource
(decision 53, phase B, 2026-10-03).

NPS's alerts for park codes `cali` and `oreg` land once, in nps/warnings.py's `nps_alerts`, whose
sources.json entry lists them against this folder in `park_codes` (decision 34). NPS's Danger,
Caution and Information categories are the warnings half, split from the rest in dbt.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 3),
    checked=(
        (
            "NPS alerts API, `parkCode=cali,oreg` (the decision 53 inventory, batch 5, 2026-10-03): 0 alerts. "
            "Landed by nps/warnings.py as nps_alerts."
        ),
        "(coverage audit, 2026-10-01) Same endpoint, Danger/Caution categories, 0 today",
        "(decision 53 inventory, batch 5, 2026-10-03) https://octa-trails.org/robots.txt answered Cloudflare's "
        "managed challenge (403, 'Just a moment...', cf-mitigated: challenge) to our agent; not solved, and no page "
        "was asked, so whether OCTA publishes notices of its own stays unknown.",
    ),
    where=(
        "https://developer.nps.gov/api/v1/alerts?parkCode=cali,oreg",
        "https://mapservices.nps.gov/arcgis/rest/services",
        "https://octa-trails.org/",
    ),
    reason=(
        "drawn from nps/'s resources, extracted once there (decision 34); checked names the layer this org's data arrives in"
    ),
)
