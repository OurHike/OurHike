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
    -- ATC publishes no public/internal split on this layer, so public_use is
    -- null: "this organization declares no such flag", never "not public".
    -- The column exists because DEC's and OPRHP's layers do publish one, and
    -- the union is positional (DBT.md's ST06 prune) - see
    -- stg_dec__lean_tos for what the flag means and why it is carried
    -- rather than applied.
    cast(null as varchar) as public_use,
    st_x(geom) as longitude,
    st_y(geom) as latitude,
    _loaded_at as loaded_at
from source
