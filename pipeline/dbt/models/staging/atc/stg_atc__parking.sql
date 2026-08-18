-- Same shape as stg_atc__shelters, same reasoning - see that model. The
-- poi_type/confidence/source literals mirror export_poi.py's DIRECT_SOURCES
-- row for this layer, held together by test_dbt_seed_sync.py via the seed.
with source as (
    select * from {{ source('atc', 'raw_atc__parking') }}
)

select
    'atc_parking' as source,
    cast(globalid as varchar) as source_id,
    name,
    'parking' as poi_type,
    'high' as confidence,
    st_x(geom) as longitude,
    st_y(geom) as latitude,
    _loaded_at as loaded_at
from source
