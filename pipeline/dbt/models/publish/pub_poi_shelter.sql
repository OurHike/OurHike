{{ config(format='json', location='poi_shelter.geojson') }}
-- poi_shelter.geojson: the A.T. family's shelter POIs, in the shape
-- export_poi.py's write_poi_type() has GDAL write it
-- (macros/poi_feature_collection.sql).
with pois as (
    select * from {{ ref('points_of_interest') }}
    where phone_files = 'poi_by_type'
)

{{ poi_by_type_feature_collection('pois', 'shelter') }}
