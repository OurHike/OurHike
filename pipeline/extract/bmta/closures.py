"""Benton MacKaye Trail Association: closures, drawn from nps/warnings.py's NPS alerts resource
(decision 53, phase B, 2026-10-03).

NPS's alerts for park code `grsm` land once, in nps/warnings.py's `nps_alerts`, whose sources.json
entry lists it against this folder in `park_codes` (decision 34). NPS's `Park Closure` category is
the closures half, split from the rest in dbt; a Park Closure most often closes a facility or a road
rather than a trail, and no alert carries geometry, so it never sets `obstructs_trail` alone.

The inventory also found a PDF, a web page for this club, which other phase B readers take; if one
lands for this type it takes this file, and this note becomes a line in its docstring.

The coverage audit's note, kept as it was (restated from reference/org_coverage.json, whose text is
trimmed where it ends in '…'):

PDF. Also `bmtamail.org/docs/KnowBeforeYouGo.pdf`.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 3),
    checked=(
        (
            "NPS alerts API, `parkCode=grsm` (the decision 53 inventory, batch 3, 2026-10-03): 3 (Park Closure "
            "'Park Headquarters Road is closed' 2026-06-26; Park Closure 'Straight Fork ... Balsam Mountain Road "
            "closed' 2025-11-12; Information 'Most visitors need a parking tag'). Tiebreak for the GSMNP fire-ban "
            "disagreement. Landed by nps/warnings.py as nps_alerts."
        ),
        (
            '(coverage audit, 2026-10-01) "Current Alerts & Advisories", '
            "`https://bmtamail.org/docs/CurrentAlertsandAdvisories.pdf`: a 1-page PDF, Last-Modified 2026-09-09, "
            "289,535 B. It held 0 closure items today, but it is the channel the BMTA posts to."
        ),
    ),
    where=(
        "https://developer.nps.gov/api/v1/alerts?parkCode=grsm",
        "https://bmtamail.org/docs/CurrentAlertsandAdvisories.pdf",
        "https://bmtamail.org/docs/KnowBeforeYouGo.pdf",
    ),
    reason=(
        "drawn from nps/'s resources, extracted once there (decision 34); checked names the layer this org's data arrives in"
    ),
)
