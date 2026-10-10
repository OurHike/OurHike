"""The Great Smokies' backcountry shelters, with the park's own capacities, and the NPS API's campgrounds.

Read live 2026-10-03 for decision 54's wave 1. NPS's nationwide point layer, NPS_Public_POIs, is its
own trail_orgs.json row, nps-poi, and is extracted once there, in nps_poi/points_of_interest.py.

Decision 54, wave 3 (2026-10-04): `nps_api_campgrounds`, the NPS Data API's /campgrounds, 665
nationally by the API's own total (one request with api.data.gov's public demo key). It needs
NPS_API_KEY, which refresh-reference.yml's extract job passes from the repository's secret; a run
without the secret withdraws the table as unavailable, never reads it as empty
(extract/_ogc.py's JsonFeatures). The clubs whose
point cells name it (natr, semo) draw their portion by `parkCode` in dbt (decision 34). Not
registered: /visitorcenters, which answered 429 on the demo key, so nothing was read of it.
"""

from extract._kinds import arcgis_layer
from extract._ogc import json_features

CLAIMS = ("nps_grsm_backcountry_shelters", "nps_api_campgrounds")
RESOURCES = [arcgis_layer("nps_grsm_backcountry_shelters"), json_features("nps_api_campgrounds")]
