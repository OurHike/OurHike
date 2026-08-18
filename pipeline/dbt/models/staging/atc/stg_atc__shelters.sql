-- One source in, light rename/cast only (DBT.md's staging convention).
-- poi_type/confidence/source literals mirror export_poi.py's ATC_EXPORTS
-- row for this layer; the seed carries the same pair and
-- test_dbt_seed_sync.py holds all three together.
with source as (
    select * from {{ source('atc', 'raw_atc__shelters') }}
)

select
    'atc_shelters' as source,
    cast(globalid as varchar) as source_id,
    name,
    'shelter' as poi_type,
    'high' as confidence,
    st_x(geom) as longitude,
    st_y(geom) as latitude,
    _loaded_at as loaded_at
from source
