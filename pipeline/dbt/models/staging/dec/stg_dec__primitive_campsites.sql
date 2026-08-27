-- DEC's primitive campsites, same shape and same reasoning as
-- stg_dec__lean_tos - read that model for what every literal rests on and
-- for why PUBLICUSE is carried rather than applied.
--
-- The largest single block of POIs Phase D adds: 2,078 rows statewide,
-- counted live 2026-08-27. These are BACKCOUNTRY sites and one row is one
-- tent site, which is the difference sources.json records against OPRHP's
-- campsite rows, where one row is a whole drive-in campground. Nothing here
-- encodes that difference - it is a note for whoever unifies the two, not a
-- column this layer publishes.
with source as (
    select * from {{ source('dec', 'raw_dec__dec_primitive_campsites') }}
)

select
    'dec_primitive_campsites' as source,
    cast(objectid as varchar) as source_id,
    name,
    'campsite' as poi_type,
    'high' as confidence,
    publicuse as public_use,
    st_x(geom) as longitude,
    st_y(geom) as latitude,
    _loaded_at as loaded_at
from source
