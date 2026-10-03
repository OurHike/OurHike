"""Natchez Trace NST (NPS-administered): closures, drawn from nps/warnings.py's NPS alerts resource
(decision 53, phase B, 2026-10-03).

NPS's alerts for park code `natr` land once, in nps/warnings.py's `nps_alerts`, whose sources.json
entry lists it against this folder in `park_codes` (decision 34). NPS's `Park Closure` category is
the closures half, split from the rest in dbt; a Park Closure most often closes a facility or a road
rather than a trail, and no alert carries geometry, so it never sets `obstructs_trail` alone.

The inventory also found a web page for this club, which other phase B readers take; if one lands
for this type it takes this file, and this note becomes a line in its docstring.

The coverage audit's note, kept as it was (restated from reference/org_coverage.json, whose text is
trimmed where it ends in '…'):

API plus page. The road closures are parkway (driving) closures, and most do not close the footpath.
Skeptic spot-check: the alerts API returns 1 `natr` alert, category Park Closure. The status page
still reads "No Current Trail or Campground Closures — Last updated: August 14, 2026".
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
        (
            '(coverage audit, 2026-10-01) NPS alerts API `natr`: 1 ("Current Park Closures", category Park '
            "Closure). That alert points to `https://www.nps.gov/natr/planyourvisit/road-and-site-status.htm`, "
            'which reads "No Current Trail or Campground Closures — Last updated: August 14, 2026" and lists road '
            'closures (e.g. "MP 437-440 - Closed for Bridge Construction", April 2026–May 2027).'
        ),
    ),
    where=(
        "https://developer.nps.gov/api/v1/alerts?parkCode=natr",
        "https://www.nps.gov/natr/planyourvisit/road-and-site-status.htm",
    ),
    reason=(
        "drawn from nps/'s resources, extracted once there (decision 34); checked names the layer this org's data arrives in"
    ),
)
