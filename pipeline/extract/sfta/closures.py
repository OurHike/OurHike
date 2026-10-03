"""Santa Fe Trail Association: closures, drawn from nps/warnings.py's NPS alerts resource (decision 53,
phase B, 2026-10-03).

NPS's alerts for park code `safe` land once, in nps/warnings.py's `nps_alerts`, whose sources.json
entry lists it against this folder in `park_codes` (decision 34). NPS's `Park Closure` category is
the closures half, split from the rest in dbt; a Park Closure most often closes a facility or a road
rather than a trail, and no alert carries geometry, so it never sets `obstructs_trail` alone.

The association's own site is walled: https://www.santafetrail.org/ answered our agent with SiteGround's
captcha challenge (HTTP 202, `sg-captcha: challenge`, a 169-byte meta refresh to
/.well-known/sgcaptcha/), and its robots.txt answered the same (decision 53's inventory, batch 3,
2026-10-03). Not solved, not retried (decision 39), so whether it publishes notices stays unknown.

The coverage audit's note, kept as it was (restated from reference/org_coverage.json, whose text is
trimmed where it ends in '…'):

Own: UNKNOWN
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 3),
    checked=(
        "(decision 53 inventory, batch 3, 2026-10-03) https://www.santafetrail.org/ and its robots.txt answered "
        "SiteGround's captcha challenge (202, sg-captcha: challenge) to our agent; not solved, not retried.",
        (
            "NPS alerts API, `parkCode=safe` (the decision 53 inventory, batch 3, 2026-10-03): 0 alerts. Allowed "
            "zero: total=0 for safe. Landed by nps/warnings.py as nps_alerts."
        ),
        "(coverage audit, 2026-10-01) `NPSAPI/alerts?parkCode=safe`: 0 today",
    ),
    where=(
        "https://developer.nps.gov/api/v1/alerts?parkCode=safe",
        "https://mapservices.nps.gov/arcgis/rest/services",
        "https://santafetrail.org/",
    ),
    reason=(
        "drawn from nps/'s resources, extracted once there (decision 34); checked names the layer this org's data arrives in"
    ),
)
