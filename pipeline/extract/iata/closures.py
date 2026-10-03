"""Ice Age Trail Alliance: closures, drawn from nps/warnings.py's NPS alerts resource (decision 53,
phase B, 2026-10-03).

NPS's alerts for park code `iatr` land once, in nps/warnings.py's `nps_alerts`, whose sources.json
entry lists it against this folder in `park_codes` (decision 34). NPS's `Park Closure` category is
the closures half, split from the rest in dbt; a Park Closure most often closes a facility or a road
rather than a trail, and no alert carries geometry, so it never sets `obstructs_trail` alone.

The inventory also found a web page, an ArcGIS layer for this club, which other phase B readers
take; if one lands for this type it takes this file, and this note becomes a line in its docstring.

The coverage audit's note, kept as it was (restated from reference/org_coverage.json, whose text is
trimmed where it ends in '…'):

Filter `posted='yes'`. The 57 `no` rows include alerts from as far back as 2019 ("Stewart Tunnel
closed", posted 2019-09). Loading all 80 would show expired closures as live. Gun-deer closures are
lines that close segments, so they `obstruct_trail` (decision 7). The NPS copy must be deduplicated
…
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 3),
    checked=(
        (
            "NPS alerts API, `parkCode=iatr` (the decision 53 inventory, batch 3, 2026-10-03): 16 (Information "
            "11, all titled 'Reroute in Effect — ...'; Caution 5 'Use Caution — ...'). The same events "
            "republished by NPS; dedup against the IATA layer in dbt. NPS category cannot drive obstructs_trail. "
            "Landed by nps/warnings.py as nps_alerts."
        ),
        (
            "(coverage audit, 2026-10-01) `.../IAT_Trail_Conditions_Posted/FeatureServer/0`: 80 rows, last edit "
            "2026-09-30. `posted`: yes 21, no 57, pending 2. Headings include Trail Closed 5, Trail closure 4, "
            'Logging Closure 3, Prescribed Burn Closure 2, Boardwalk Closed, Bridge Closed, and "Hunting Closure '
            'beginning 9/1 / 10/15 / 11/2 / 11/22". Fields: `date_posted`, `date_updated`, `hyperlink`, '
            "`segment_name`. `.../IAT_Hunting_Closures/FeatureServer/0`: 52 polylines (`GunDeer` = Closed on 51, "
            "`OtherSeason` = Closed on 6), last edit 2026-09-21. The NPS Data API `alerts?parkCode=iatr` returns "
            '16 (11 "Reroute in Effect", 5 "Use …'
        ),
    ),
    where=(
        "https://developer.nps.gov/api/v1/alerts?parkCode=iatr",
        "https://dnrmaps.wi.gov/arcgis/rest/services",
        "https://iceagetrail.org/",
    ),
    reason=(
        "drawn from nps/'s resources, extracted once there (decision 34); checked names the layer this org's data arrives in"
    ),
)
