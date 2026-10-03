{{ config(format='json', location='poi_viewpoint.geojson') }}
-- poi_viewpoint.geojson: the A.T. family's viewpoint POIs, in the shape
-- export_poi.py's write_poi_type() has GDAL write it
-- (macros/poi_feature_collection.sql).
with pois as (
    select * from {{ ref('points_of_interest', v=1) }}
    where phone_files = 'poi_by_type'
)

{{ poi_by_type_feature_collection('pois', 'viewpoint') }}
