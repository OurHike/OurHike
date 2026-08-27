-- DEC's firetowers as `viewpoint`, same shape and reasoning as
-- stg_dec__lean_tos. 35 rows, counted live 2026-08-27.
--
-- @unvalidated - the poi_type is sources.json's declared call and it carries
-- its own caveat, repeated here because a staging model is where a consumer
-- will actually look: a restored tower is a thing hikers climb for the view,
-- but a hiker who reaches a CLOSED one finds a locked cab, and this layer
-- publishes no open/closed state to tell them apart. What would settle it is
-- DEC's own tower-status list, which is prose on their website rather than a
-- field here. Nothing in this model may be read as "the tower is climbable".
with source as (
    select * from {{ source('dec', 'raw_dec__dec_firetowers') }}
)

select
    'dec_firetowers' as source,
    cast(objectid as varchar) as source_id,
    name,
    'viewpoint' as poi_type,
    'high' as confidence,
    publicuse as public_use,
    st_x(geom) as longitude,
    st_y(geom) as latitude,
    _loaded_at as loaded_at
from source
