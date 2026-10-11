"""New York State Canal Corporation: warnings (decision 122's held load, here since the Canal Corporation's row;
closures.py says how this folder came to be).

- `nys_canal_trail_condition`: `Centerline_Condition/FeatureServer/0`, the Canalway Trail's centerline in 764
  segments, each surface Good, Fair or Poor, from a 2022 field survey (last edited 2022-02-01): a condition then,
  not an alert now.

On the hourly lane's notices job, as every closures and warnings source is (decision 61); one conditional GET a run
while nothing moves.
"""

from extract._kinds import arcgis_layer

CLAIMS = ("nys_canal_trail_condition",)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
