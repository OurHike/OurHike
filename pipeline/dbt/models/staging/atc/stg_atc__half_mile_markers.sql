-- ATC's own mile scale - the calibration authority for the whole mile axis
-- (#652): export_elevation and every published POI mile ride these values.
-- Point_ID is the identity; the layer has no GlobalID.
with source as (
    select * from {{ source('atc', 'raw_atc__half_mile_points_from_springer') }}
)

select
    cast(point_id as varchar) as source_id,
    measure as measure_mi,
    measurem as measure_m,
    st_x(geom) as longitude,
    st_y(geom) as latitude,
    _loaded_at as loaded_at
from source
