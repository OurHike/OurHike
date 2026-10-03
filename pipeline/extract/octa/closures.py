"""Oregon-California Trails Association: closures, drawn from nps/warnings.py's NPS alerts resource
(decision 53, phase B, 2026-10-03).

NPS's alerts for park codes `cali` and `oreg` land once, in nps/warnings.py's `nps_alerts`, whose
sources.json entry lists them against this folder in `park_codes` (decision 34). NPS's `Park
Closure` category is the closures half, split from the rest in dbt; a Park Closure most often closes
a facility or a road rather than a trail, and no alert carries geometry, so it never sets
`obstructs_trail` alone.

The coverage audit's note, kept as it was (restated from reference/org_coverage.json, whose text is
trimmed where it ends in '…'):

Whether OCTA publishes its own is UNKNOWN (403)
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
        "(coverage audit, 2026-10-01) `NPSAPI/alerts?parkCode=oreg,cali`: 0 alerts on 2026-10-01 (JSON API)",
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
