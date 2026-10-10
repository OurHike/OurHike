"""National Park Service: warnings, from NPS's alerts API and its road events feed, hourly (decision 53, phase B).

`nps_alerts` reads every park code sources.json's entry lists in `park_codes`,
in one request, and that map also names the club folders drawing on each
code; their closures.py and warnings.py are `via` notes naming this file
(decision 34). Every alert lands once, whatever its `category`: Danger,
Caution and Information feed warnings, and Park Closure feeds closures, each
split made in dbt; nps/closures.py holds the park closure layers and its
staging model reads `raw_nps__nps_alerts` for that half. `nps_road_events` is
NPS's national WZDx feed, a road closed to a trailhead being the "unable to
get off the trail quickly" case.

WHAT THIS DOES NOT READ: the units no club folder names. nps_trails and
nps_poi/ are national, and the API's national list held 622 alerts on
2026-10-03, so a hiker on a trail in an unlisted park gets no NPS alert from
here. Reading them all is two pages an hour and the maintainer's call
(sources.json's `park_codes_comment`).

Both need NPS_API_KEY (extract/_json_apis.py, "THE KEY"); without it the two
tables are withdrawn, never read as no alerts.

One ArcGIS park layer is extracted here too (decision 53 phase B, 2026-10-03):

- `nps_yose_fire_restrictions`: Yosemite fire restriction stages,
  `YOSE_FireRestrictionStages/FeatureServer/0`, 147 polygons when the coverage audit measured it
  (2026-10-01). Its row in sources.json holds its counts, dates and terms; the change check is
  _kinds.py's ArcgisLayer, a conditional GET of the layer document on ArcGIS Online, and an
  allowed zero only beside the server's own returnCountOnly read in the same run.

`YOSE_RockFall_HazardLine_YosemiteValley/FeatureServer/0` (12 lines, coverage audit 2026-10-01)
has no sources.json row: the phase A inventory did not list it, so phase B did not read it.

Two alerts bear on water and are not drought (coverage audit, 2026-10-01): grca "INNER CANYON
WATER SHUTOFFS" (Danger) and grfa "Public restrooms closed … no drinking water". They belong next
to the water card, not in warnings alone. Maintainer call.

ArcGIS layers read and not wired as closures or warnings (decision 53 phase B, 2026-10-03):
https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services/GRSM_ROADS/FeatureServer/0,
GRSM's roads, 697 of 1,925 'Temporarily Closed' and unedited since 2025-11-13: a seasonal road
attribute, not a current notice.
"""

from extract._json_apis import nps_alerts, nps_road_events
from extract._kinds import arcgis_layer

CLAIMS = ("nps_alerts", "nps_road_events", "nps_yose_fire_restrictions")
RESOURCES = [
    nps_alerts("nps_alerts"),
    nps_road_events("nps_road_events"),
    arcgis_layer("nps_yose_fire_restrictions"),
]
