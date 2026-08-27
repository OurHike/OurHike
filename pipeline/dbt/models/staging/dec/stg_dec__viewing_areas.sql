-- DEC's viewing areas as `viewpoint`, same shape and reasoning as
-- stg_dec__lean_tos. 34 rows, counted live 2026-08-27.
--
-- The layer's own name carries a leading space in DEC's service metadata
-- (' Viewing Area'), which sources.json records as hygiene rather than
-- meaning. Nothing here matches on it.
with source as (
    select * from {{ source('dec', 'raw_dec__dec_viewing_areas') }}
)

select
    'dec_viewing_areas' as source,
    cast(objectid as varchar) as source_id,
    name,
    'viewpoint' as poi_type,
    'high' as confidence,
    publicuse as public_use,
    st_x(geom) as longitude,
    st_y(geom) as latitude,
    _loaded_at as loaded_at
from source
