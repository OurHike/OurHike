"""Finger Lakes Trail Conference: the FLT system's own lines, from FLTC's ArcGIS Online organization, the
three line layers of its public web map 'FLT System Master' (item 9794ff6ba02d4c25b809d1a73c388fc3),
which the Experience Builder app at fingerlakestrail.org/map/ embeds. Its third line layer,
`Hunting_Bypasses_/FeatureServer/2` (69 hunting and high-water bypasses), is `fltc_hunting_bypasses`,
which warnings.py claims (decision 53, 2026-10-03), so it is extracted there once and not here.

Decision 54, wave 1: read live on 2026-10-03 (robots.txt first, lib/user_agent.py's agent, 2 s or more
between requests to one host) and registered in sources.json, where each row carries the count, extent,
statistics fingerprint, measured key, person fields and the item's own terms.

- `fltc_flt_main`: Finger Lakes Trail: thru trails, loops and spurs (FLTC). 225 lines, keyed on geometry.
- `fltc_non_flt_trails`: Non-FLT trails near the Finger Lakes Trail (FLTC). 215 lines, keyed on geometry.

FLTC's website was not fetched: its robots.txt disallows /FLTC/, and the map's layers are read from
ArcGIS Online, not the site. The map's Closures_, Waypoints and Temporary_Notices layers are other
workers' types. Not landed: `FLTmain_harold` (224 lines), by its own description a 'Copy of June 6, 2025
FLT tracks for Harold to experiment with' in a personal account, not FLTC's publication. The two M27
layers, a reroute after a 'Loss of permission between SF and Delaware CR 27', are copies of part of the
main layers (SAME_AS below): every line in them is also in the main layers, so FLTC has carried the
reroute into those (Reasoned from the geometry match).
"""

from datetime import date

from extract._contract import SameAs
from extract._kinds import arcgis_layer

CLAIMS = (
    "fltc_flt_main",
    "fltc_non_flt_trails",
)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]

SAME_AS = (
    SameAs(
        original="fltc_flt_main",
        copy=("https://services7.arcgis.com/GwV4OWqOyYWWUpBK/arcgis/rest/services/M27FLTmain/FeatureServer/13",),
        confirmed=date(2026, 10, 3),
        checked=(
            "Every one of its 7 distinct geometries (12 rows) is also in FLTmain/1, vertex for vertex at 6 "
            "decimals, with the same 13 fields (compared 2026-10-03); FLTmain was last edited 2026-07-20, "
            "three days after it",
        ),
    ),
    SameAs(
        original="fltc_hunting_bypasses",
        copy=("https://services7.arcgis.com/GwV4OWqOyYWWUpBK/arcgis/rest/services/M27M28Hunting_Bypasses/FeatureServer/18",),
        confirmed=date(2026, 10, 3),
        checked=(
            "Its one line is also in Hunting_Bypasses_/2, vertex for vertex at 6 decimals, with the same 8 "
            "fields (compared 2026-10-03)",
        ),
    ),
)
