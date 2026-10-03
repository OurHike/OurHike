"""The Trail Conservancy (Austin): the Ann and Roy Butler Hike and Bike Trail around Lady Bird Lake.

The organization is reference/trail_orgs.json's 'The Trail Foundation (Austin)', registered in sources.json as
The Trail Conservancy (org:ttc), whose initials its ArcGIS Online layers' TTC prefix matches.

Decision 54, wave 1: read live on 2026-10-03 (robots.txt first, lib/user_agent.py's agent, 2 s or more
between requests to one host) and registered in sources.json, where each row carries the count, extent,
statistics fingerprint, measured key, person fields and the item's own terms.

- `ttc_butler_trail`: Ann and Roy Butler Hike and Bike Trail (The Trail Conservancy). 237 lines, keyed on `GlobalID_2`.
- `austin_pard_trails`: Austin Parks and Recreation trails on parkland (City of Austin PARD). 4,096 lines, keyed on `ASSET_MGMT_ID`.

Two datasets of the same ground: TTC's own Butler Trail layer, built from the city's data and edited
apart since, and the City of Austin PARD's trail inventory, which is also the line tx_tamers/'s Violet
Crown Trail work sits on. Not landed, each a working layer of the same trail on TTC's organization and
read 2026-10-03: `Butler_Trail_clipped` (278, a February 2025 derivative of Butler_Trail), `trail_route`
(248) and `hikers_route` (120), 2020 editions of the same route, `Pard_trails_RECA` (5 rows of PARD's
schema at one site), and `Adjacent_Trails` (227), OpenStreetMap ways carrying their osm_id, a copy of
OSM, whose ODbL terms would travel with it.
"""

from extract._kinds import arcgis_layer

CLAIMS = (
    "ttc_butler_trail",
    "austin_pard_trails",
)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
