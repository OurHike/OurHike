"""National Park Service: warnings, from NPS's alerts API and its road events feed, hourly (decision 53, phase B).

`nps_alerts` reads every park code sources.json's entry lists in `park_codes`,
in one request, and that map also names the club folders drawing on each
code; their closures.py and warnings.py are `via` notes naming this file
(decision 34). Every alert lands once, whatever its `category`: Danger,
Caution and Information feed warnings, and nps/closures.py SHARES this file
for Park Closure, each split made in dbt. `nps_road_events` is NPS's national
WZDx feed, a road closed to a trailhead being the "unable to get off the
trail quickly" case.

WHAT THIS DOES NOT READ: the units no club folder names. nps_trails and
nps_poi/ are national, and the API's national list held 622 alerts on
2026-10-03, so a hiker on a trail in an unlisted park gets no NPS alert from
here. Reading them all is two pages an hour and the maintainer's call
(sources.json's `park_codes_comment`).

Both need NPS_API_KEY (extract/_json_apis.py, "THE KEY"); without it the two
tables are withdrawn, never read as no alerts.

The coverage audit's other NPS warnings, ArcGIS park layers it measured on
2026-10-01 (`YOSE_FireRestrictionStages/FeatureServer/0`, 147 polygons;
`YOSE_RockFall_HazardLine_YosemiteValley/FeatureServer/0`, 12 lines), have
no sources.json row yet: they are decision 54 wave 1's, and join this file's
CLAIMS when registered.
"""

from extract._json_apis import nps_alerts, nps_road_events

CLAIMS = ("nps_alerts", "nps_road_events")
RESOURCES = [nps_alerts("nps_alerts"), nps_road_events("nps_road_events")]
