-- The one sanctioned join in staging (DBT.md names it): resolving the raw
-- `icon` code to a unified poi_type through the poi_type_mapping seed. A
-- left join, deliberately - a waypoint whose icon is documented-but-unmapped
-- keeps its row with a null poi_type rather than disappearing, so every
-- layer stays 1:1 with its input and the row-count reconciliation tests
-- keep meaning something.
with source as (
    select * from {{ source('opentrail', 'raw_opentrail__at') }}
),

mapping as (
    select
        code,
        poi_type,
        confidence
    from {{ ref('poi_type_mapping') }}
    where source_system = 'opentrail'
)

select
    'opentrail_at' as source,
    cast(source.dbid as varchar) as source_id,
    source.title as name,
    mapping.poi_type,
    mapping.confidence,
    -- opentrail publishes no public/internal split, so public_use is null:
    -- "this source declares no such flag", never "not public". The column
    -- exists because DEC's and OPRHP's layers do publish one, and the union
    -- is positional (DBT.md's ST06 prune) - see stg_dec__lean_tos for what
    -- the flag means and why it is carried rather than applied.
    cast(null as varchar) as public_use,
    st_x(source.geom) as longitude,
    st_y(source.geom) as latitude,
    source._loaded_at as loaded_at
from source
left join mapping on source.icon = mapping.code
