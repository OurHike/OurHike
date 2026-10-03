"""Lewis & Clark Trail Heritage Foundation: closures, drawn from nps/warnings.py's NPS alerts resource
(decision 53, phase B, 2026-10-03).

NPS's alerts for park code `lecl` land once, in nps/warnings.py's `nps_alerts`, whose sources.json
entry lists it against this folder in `park_codes` (decision 34). NPS's `Park Closure` category is
the closures half, split from the rest in dbt; a Park Closure most often closes a facility or a road
rather than a trail, and no alert carries geometry, so it never sets `obstructs_trail` alone.

The club's own site holds no notice: the decision 53 inventory (batch 3, 2026-10-03) read
https://lewisandclark.org/wp-json/wp/v2/search?search=closure&per_page=20, and WordPress's own
search for 'closure' answered an empty list. So nothing of the club's own is wired here (phase B,
pages, feeds and WordPress, 2026-10-03).

The coverage audit's note, kept as it was (restated from reference/org_coverage.json, whose text is
trimmed where it ends in '…'):

Own: `search?search=closure` 0
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 3),
    checked=(
        "NPS alerts API, `parkCode=lecl` (the decision 53 inventory, batch 3, 2026-10-03): 0 alerts. Allowed zero: total=0 for lecl. Landed by nps/warnings.py as nps_alerts.",
        "(coverage audit, 2026-10-01) `NPSAPI/alerts?parkCode=lecl`: 0 today",
        "(the decision 53 inventory, batch 3, 2026-10-03) https://lewisandclark.org/wp-json/wp/v2/search?search=closure&per_page=20: WordPress's own search for 'closure' answered an empty list.",
    ),
    where=(
        "https://developer.nps.gov/api/v1/alerts?parkCode=lecl",
        "https://mapservices.nps.gov/arcgis/rest/services",
        "https://lewisandclark.org/",
    ),
    reason="drawn from nps/'s resources, extracted once there (decision 34); checked names the layer this org's data arrives in",
)
