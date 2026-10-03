"""Benton MacKaye Trail Association: warnings, drawn from nps/warnings.py's NPS alerts resource
(decision 53, phase B, 2026-10-03).

NPS's alerts for park code `grsm` land once, in nps/warnings.py's `nps_alerts`, whose sources.json
entry lists it against this folder in `park_codes` (decision 34). NPS's Danger, Caution and
Information categories are the warnings half, split from the rest in dbt.

The inventory also found a PDF, a web page for this club, which other phase B readers take; if one
lands for this type it takes this file, and this note becomes a line in its docstring.

The coverage audit's note, kept as it was (restated from reference/org_coverage.json, whose text is
trimmed where it ends in '…'):

Staleness risk: April restrictions are still listed in a September file, with no per-item end dates.
Whether they still hold is unverified, so these must not be shown as current without a USFS
cross-check. Skeptic, a second channel that contradicts the first: every `bmta.org` page carries a …
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
            "(coverage audit, 2026-10-01) The same PDF has 5 notices: fireworks always prohibited; Chattahoochee "
            'Stage II fire restriction "lifted 5/4/2026"; Cherokee NF Stage 1 fire restrictions "beginning April '
            '24, 2026"; Nantahala campfire ban "April 15, 2026"; GSMNP parkwide fire ban cancelled. Also '
            "`bmtamail.org/docs/BeBearPreparedontheBMT.pdf` (static)."
        ),
    ),
    where=(
        "https://developer.nps.gov/api/v1/alerts?parkCode=grsm",
        "https://bmtamail.org/docs/BeBearPreparedontheBMT.pdf",
        "https://bmta.org",
    ),
    reason=(
        "drawn from nps/'s resources, extracted once there (decision 34); checked names the layer this org's data arrives in"
    ),
)
