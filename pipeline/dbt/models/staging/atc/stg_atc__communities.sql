-- The resupply PROXY: a town being an official A.T. Community says supply
-- is probably there, not that anyone verified a store - which is why the
-- confidence is 'low' where the facility layers carry 'high'
-- (export_poi.py's DIRECT_SOURCES row, held by the seed sync test).
-- Upstream spells the column NAME, not the facilities family's Name -
-- DuckDB resolves identifiers case-insensitively so the reference below
-- reads the same either way, but export_poi.py's field_map (which is
-- case-sensitive JSON) has to spell it upstream's way.
with source as (
    select * from {{ source('atc', 'raw_atc__communities') }}
)

select
    'atc_communities' as source,
    cast(globalid as varchar) as source_id,
    name,
    'resupply' as poi_type,
    'low' as confidence,
    st_x(geom) as longitude,
    st_y(geom) as latitude,
    _loaded_at as loaded_at
from source
