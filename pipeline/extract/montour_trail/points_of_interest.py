"""Montour Trail Council: points of interest. The council's trail_orgs.json row, `montour-trail` (`load: via`, its line
PASDA's beside its own route layer), was approved on 2026-10-11 (decision 121, review page 01), so these files moved
here from _shared/montour_trail/, where decision 122 had loaded them held, and every raw table kept its name.

- `montour_trail_access_areas`: `Access_Areas_View/FeatureServer/3`, the trail's 37 access areas with their
  amenities as columns (2026-10-09): a drinking fountain at 9, a shelter at 5.

Its alerts page is closures.py's. Its dated alerts are events in its calendar's JSON, which need a reader nothing has
yet, and wait with its other layers. make_dbt_staging.py stages these points now that the steward has a folder of its
own; no seeds/club_poi_types.csv row reads its amenity columns yet, so none of them publishes until one does. Monthly.
"""

from extract._kinds import arcgis_layer

CLAIMS = ("montour_trail_access_areas",)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
