-- Same shape as stg_atc__shelters, same reasoning - see that model.
with source as (
    select * from {{ source('atc', 'raw_atc__campsites') }}
)

select
    'atc_campsites' as source,
    cast(globalid as varchar) as source_id,
    name,
    'campsite' as poi_type,
    'high' as confidence,
    st_x(geom) as longitude,
    st_y(geom) as latitude,
    _loaded_at as loaded_at
from source
