"""Missouri State Parks: closures, held. A candidate steward with no trail_orgs.json row yet, so it lives in
_shared/ under the folder its row would name (decision 122, the maintainer's poll, 2026-10-09: "Every type, held").
Every row is held until the maintainer approves the steward's trail_orgs.json row in chat (decision 121); when it
is written, these files move to the club folder of the same name and every raw table keeps its name.

- `mo_state_parks_trail_advisories`: `parks/Trail_Advisory_Viewer/MapServer/13`, the Katy and Rock Island
  trails' advisories by mile marker, each with its own status and dates (4 rows on 2026-10-09).
- `mo_state_parks_katy_trailheads`: `parks/Trail_Advisory_Viewer/MapServer/0`, the Katy Trail's 26 trailheads,
  each with its own status (Open, Caution or Closed).

Both are on the DNR's own on-prem server. The advisories layer has no maintained date, so its change check
answers UNKNOWN and it is read whole every notices run (4 rows); the trailheads' check is the statistics
fingerprint on LAST_EDITED_DATE (each row's `freshness`). Being closures, both ride the hourly lane's notices
job (extract/_run.py's job_of(), decision 61), never the conditions job.
"""

from extract._kinds import arcgis_layer

TYPE = "closures"
CLAIMS = ("mo_state_parks_trail_advisories", "mo_state_parks_katy_trailheads")
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
