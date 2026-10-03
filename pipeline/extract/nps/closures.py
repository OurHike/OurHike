"""National Park Service: closures, 6 ArcGIS park layers extracted here (decision 53 phase B, 2026-10-03).

- `nps_grca_closures`: Grand Canyon National Park closures, `GRCAclosuresNPmapMay/FeatureServer/0`.
- `nps_seki_closures`: Sequoia and Kings Canyon administrative closures,
  `SEKI_Administrative_Closures_Public/FeatureServer/1`.
- `nps_yose_trail_closures`: Yosemite trail closures, `YOSE_Closures_public/FeatureServer/12`.
- `nps_yell_bear_management_areas`: Yellowstone bear management areas,
  `YELL_BEAR_MANAGEMENT_AREAS_public_viewview/FeatureServer/0`.
- `nps_appa_helene_status`: A.T. post-Hurricane Helene status centerline (NPS),
  `APPA_HeleneStatusCenterline/FeatureServer/0`.
- `grsm_trails_access`: Great Smoky Mountains NP trails: access not open,
  `GRSM_TRAILS/FeatureServer/0`. Filtered on the agency's own status field: `ACCESS <> 'Open' OR
  ACCESS IS NULL`.

Each layer's row in sources.json holds its counts, dates, terms and the person fields it never
loads. Change checks are _kinds.py's ArcgisLayer: a conditional GET of the layer document on ArcGIS
Online, the statistics fingerprint on an on-prem server, and an allowed zero only beside the
server's own returnCountOnly read in the same run.

THE ALERTS ARE THE OTHER HALF, AND THEY LAND IN nps/warnings.py. This file used to be
`SHARES = "warnings"`, and its own docstring said these park layers would become its CLAIMS when
registered and the SHARES line would move here as prose, since a file takes one form. So: one
upstream is one resource (decision 34), the alerts land once, as `nps_alerts` and
`nps_road_events` in nps/warnings.py, and the closures staging model still reads
`raw_nps__nps_alerts` for the closures half. NPS's `Park Closure` category is that half, and a road
event whose `vehicle_impact` is `all-lanes-closed` may be too; both are split in dbt. A Park
Closure most often closes a facility or a road rather than a trail (semo's two on 2026-10-03 closed
visitor centres), and no alert carries geometry, so `obstructs_trail` cannot come from the category
alone (decision 7). The park layers above do carry geometry, for the parks that publish them.

The coverage audit also counted `TRLSTATUS='Temporarily Closed'` on 60
features of nps_trails, which nps/trail_lines.py already lands (2026-10-01):
a closure status on the line itself, for dbt to read beside these alerts.

ArcGIS layers read and not wired as closures or warnings (decision 53 phase B, 2026-10-03):
https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services/GRSM_ROADS/FeatureServer/0,
GRSM's roads, 697 of 1,925 'Temporarily Closed' and unedited since 2025-11-13: a seasonal road
attribute, not a current notice.
"""

from extract._kinds import arcgis_layer

CLAIMS = (
    "nps_grca_closures",
    "nps_seki_closures",
    "nps_yose_trail_closures",
    "nps_yell_bear_management_areas",
    "nps_appa_helene_status",
    "grsm_trails_access",
)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
