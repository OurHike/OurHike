"""Oregon Parks and Recreation Department: warnings, held (decision 122; see points_of_interest.py beside this file).

- `oprd_hunting_areas`: `Admin_boundaries/AD_OPRD_HUNTING_AREAS/FeatureServer/0` on the department's own server,
  89 areas at 60 parks where hunting is allowed or prohibited (2026-10-09), with no season dates.

On the hourly lane's notices job, as every closures and warnings source is (decision 61): the unions that read a
notice source build on the hourly lane alone, so a monthly one would land where no build reads it (review finding
ARC-1, tests/test_generated_notice_models.py). Its change check is the statistics fingerprint on EDITDATE, two small
requests a run while nothing moves.
"""

from extract._kinds import arcgis_layer

TYPE = "warnings"
CLAIMS = ("oprd_hunting_areas",)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
