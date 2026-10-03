"""Chesapeake Conservancy: closures, drawn from nps/warnings.py's NPS alerts resource (decision 53,
phase B, 2026-10-03).

NPS's alerts for park code `cajo` land once, in nps/warnings.py's `nps_alerts`, whose sources.json
entry lists it against this folder in `park_codes` (decision 34). NPS's `Park Closure` category is
the closures half, split from the rest in dbt; a Park Closure most often closes a facility or a road
rather than a trail, and no alert carries geometry, so it never sets `obstructs_trail` alone.

The inventory also found a web page for this club, which other phase B readers take; if one lands
for this type it takes this file, and this note becomes a line in its docstring.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 3),
    checked=(
        (
            "NPS alerts API, `parkCode=cajo` (the decision 53 inventory, batch 1, 2026-10-03): 0 alerts. "
            "developer.nps.gov/robots.txt answers 403 API_KEY_MISSING (JSON), i.e. no robots file is served. "
            "Landed by nps/warnings.py as nps_alerts."
        ),
        ("(coverage audit, 2026-10-01) `NPSAPI/alerts?parkCode=cajo`: 0. Own homepage (Webflow) has no conditions page"),
    ),
    where=(
        "https://developer.nps.gov/api/v1/alerts?parkCode=cajo",
        "https://cicgis.org/arcgis/rest/services",
        "https://mapservices.nps.gov/arcgis/rest/services",
        "https://chesapeakeconservancy.org/",
    ),
    reason=(
        "drawn from nps/'s resources, extracted once there (decision 34); checked names the layer this org's data arrives in"
    ),
)
