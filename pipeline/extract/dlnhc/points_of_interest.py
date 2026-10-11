"""Delaware & Lehigh National Heritage Corridor: points of interest. The corridor's trail_orgs.json row, `dlnhc`
(`load: via`, its line PASDA's beside its own sections), was approved on 2026-10-11 (decision 121, review page 01), so
this file moved here from _shared/dlnhc/, where decision 122 had loaded it held, and its raw table kept its name.

- `dlnhc_trailheads`: `DL_Trailheads_V2/FeatureServer/0`, the D&L Trail's 64 trailheads with their amenities
  (2026-10-09): potable water at 5, and 11 trailheads still to be built. Its `updatedBy` names the people who
  inspected each one, and is left out by the row's person_fields.

The trail map's section status (mapdata.json) needs a reader nothing has yet, and waits with the corridor's other
layers. make_dbt_staging.py stages these points now that the steward has a folder of its own; no
seeds/club_poi_types.csv row reads `water` yet, so none of them publishes until one does. Monthly.
"""

from extract._kinds import arcgis_layer

CLAIMS = ("dlnhc_trailheads",)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
