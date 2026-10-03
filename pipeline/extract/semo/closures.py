"""Selma to Montgomery NHT (NPS): closures, drawn from nps/warnings.py's NPS alerts resource (decision
53, phase B, 2026-10-03).

NPS's alerts for park code `semo` land once, in nps/warnings.py's `nps_alerts`, whose sources.json
entry lists it against this folder in `park_codes` (decision 34). NPS's `Park Closure` category is
the closures half, split from the rest in dbt; a Park Closure most often closes a facility or a road
rather than a trail, and no alert carries geometry, so it never sets `obstructs_trail` alone.

The inventory also found a web page for this club, which other phase B readers take; if one lands
for this type it takes this file, and this note becomes a line in its docstring.

The coverage audit's note, kept as it was (restated from reference/org_coverage.json, whose text is
trimmed where it ends in '…'):

The only live closures in this batch
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 3),
    checked=(
        (
            "NPS alerts API, `parkCode=semo` (the decision 53 inventory, batch 2, 2026-10-03): 2 alerts. 2 'Park "
            "Closure' alerts: 'Temporary Location - Selma Welcome Center Closed' (id "
            "A6849236-539C-4B24-BD30-084765DDFDE1, lastIndexedDate 2026-08-13) and 'Selma Interpretive Center "
            "Closed' (id C19376D2-19D1-4AA0-A5D2-8E8A9BD9E9EE, 2026-08-12). Both close facilities, not trail. "
            "Landed by nps/warnings.py as nps_alerts."
        ),
        (
            '(coverage audit, 2026-10-01) `NPSAPI/alerts?parkCode=semo`: 2 "Park Closure": "Selma Interpretive '
            'Center Closed" (renovation, "completion is expected in 2028") and "Temporary Location - Selma '
            'Welcome Center Closed" (indexed 2026-08-12/13)'
        ),
    ),
    where=(
        "https://developer.nps.gov/api/v1/alerts?parkCode=semo",
        "https://mapservices.nps.gov/arcgis/rest/services",
        "https://nps.gov/semo/",
    ),
    reason=(
        "drawn from nps/'s resources, extracted once there (decision 34); checked names the layer this org's data arrives in"
    ),
)
