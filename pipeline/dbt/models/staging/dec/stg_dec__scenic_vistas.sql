-- DEC's scenic vistas, same shape and reasoning as stg_dec__lean_tos.
-- 134 rows, counted live 2026-08-27.
--
-- One of THREE DEC services that land on `viewpoint` - the others are
-- stg_dec__firetowers and stg_dec__viewing_areas - because DEC splits by
-- asset type where lib/poi_schema.py's vocabulary splits by what a hiker
-- walks to. That is a mapping, not a merge: the three stay separate models
-- with separate `source` values, and cross-source deduplication remains
-- deferred exactly as it was in Phase A.
with source as (
    select * from {{ source('dec', 'raw_dec__dec_scenic_vistas') }}
)

select
    'dec_scenic_vistas' as source,
    cast(objectid as varchar) as source_id,
    name,
    'viewpoint' as poi_type,
    'high' as confidence,
    publicuse as public_use,
    st_x(geom) as longitude,
    st_y(geom) as latitude,
    _loaded_at as loaded_at
from source
