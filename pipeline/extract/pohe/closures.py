"""Potomac Heritage Trail Association: closures, drawn from nps/warnings.py's NPS alerts resource
(decision 53, phase B, 2026-10-03).

NPS's alerts for park code `pohe` land once, in nps/warnings.py's `nps_alerts`, whose sources.json
entry lists it against this folder in `park_codes` (decision 34). NPS's `Park Closure` category is
the closures half, split from the rest in dbt; a Park Closure most often closes a facility or a road
rather than a trail, and no alert carries geometry, so it never sets `obstructs_trail` alone.

The coverage audit's note, kept as it was (restated from reference/org_coverage.json, whose text is
trimmed where it ends in '…'):

Closures here belong to the section managers (C&O Canal NHP, NOVA Parks, Fairfax County). Nobody
publishes them as one list. The channel is NPS's: `developer.nps.gov/api/v1/alerts?parkCode=pohe`,
re-measured today at 0, while the same call returns 1 for `natr` and 16 for `iatr`. It belongs in
the …
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
            "(coverage audit, 2026-10-01) The association: no closures section (sitemap, 6 news posts; news RSS "
            "`?format=rss` exists)."
        ),
        (
            "(coverage audit, 2026-10-01) Skeptic: the RSS holds 7 items, 2022-07-05 to 2025-07-13. None is a "
            'closure; the nearest is "NoVa Parks Re-Mows at Trump National", 2022. NPS '
            '`pohe/planyourvisit/conditions.htm` says: "Please check directly with the local trail manager… for '
            'the most accurate and up-to-date information." NPS alerts API for `pohe`: 0 today.'
        ),
    ),
    where=("https://developer.nps.gov/api/v1/alerts?parkCode=pohe",),
    reason=(
        "drawn from nps/'s resources, extracted once there (decision 34); checked names the layer this org's data arrives in"
    ),
)
