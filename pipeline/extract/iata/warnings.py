"""Ice Age Trail Alliance: warnings, drawn from nps/warnings.py's NPS alerts resource (decision 53,
phase B, 2026-10-03).

NPS's alerts for park code `iatr` land once, in nps/warnings.py's `nps_alerts`, whose sources.json
entry lists it against this folder in `park_codes` (decision 34). NPS's Danger, Caution and
Information categories are the warnings half, split from the rest in dbt.

The inventory also found a web page, an ArcGIS layer for this club, which other phase B readers
take; if one lands for this type it takes this file, and this note becomes a line in its docstring.

The coverage audit's note, kept as it was (restated from reference/org_coverage.json, whose text is
trimmed where it ends in '…'):

"High Water" and "Trail Flooded" are warnings, not drought (decision 2). Skeptic spot-check:
`IATA_Lands_Hunting_Regulations_view/9` = 65, last edit 2026-07-13.
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
            "(coverage audit, 2026-10-01) The same conditions layer's non-closure headings: \"Caution - Logging "
            'Activities" 5, "Caution - logging near trail" 3, High Water 3, Storm Damage 3, Trail Flooded 2, '
            'Confusing blazes 2, hornet nests 2, "New Wood River - dangerous ford" 1. '
            "`.../IATA_Lands_Hunting_Regulations_view/FeatureServer/9`: 65 polygons. `.../IAT_Dogs_Prohibited`: 7 "
            "lines plus 6 points. Page `iceagetrail.org/explore/plan-hike/hunting-season-iata/` (blocked by "
            "robots.txt)."
        ),
    ),
    where=(
        "https://developer.nps.gov/api/v1/alerts?parkCode=iatr",
        "https://iceagetrail.org/explore/plan-hike/hunting-season-iata/",
    ),
    reason=(
        "drawn from nps/'s resources, extracted once there (decision 34); checked names the layer this org's data arrives in"
    ),
)
