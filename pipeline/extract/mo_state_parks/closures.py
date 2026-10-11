"""Missouri State Parks: closures. Its trail_orgs.json row, `mo-state-parks` (`load: ship`), was approved on 2026-10-11
(decision 121, review page 01), so these files moved here from _shared/mo_state_parks/, where decision 122 had loaded
them held, and every raw table kept its name. Whether each layer publishes is its sources.json row's `reaches_hikers`,
which int_sources__publication reads.

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

CLAIMS = ("mo_state_parks_trail_advisories", "mo_state_parks_katy_trailheads")
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
