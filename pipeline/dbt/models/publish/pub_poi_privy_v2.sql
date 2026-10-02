{{ config(format='json', location='poi_privy_v2.geojson') }}
-- v2/poi_privy.geojson, decision 44's v2 of the
-- points_of_interest mart: the A.T. family's privy POIs
-- as v1's poi_privy.geojson carries them, with each
-- position held once, as the point's coordinates at 6 decimals, and no
-- `lat` and `lon` properties (stage 6 of #1793; pipeline/ELT.md, "Making the
-- download smaller"). Every other property is v1's
-- (macros/poi_feature_collection.sql, version 2). parity.py's
-- poi_privy_v2 family holds each feature to v1's, its
-- coordinates to Python's round(x, 6) of v1's lat and lon.
with pois as (
    select * from {{ ref('points_of_interest', v=2) }}
    where phone_files = 'poi_by_type'
)

{{ poi_by_type_feature_collection('pois', 'privy', version=2) }}
