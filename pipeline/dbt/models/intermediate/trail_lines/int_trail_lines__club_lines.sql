{{ config(materialized='table') }}
-- Every line of the clubs' registered trail-line layers (decision 54's wave
-- 1, int_trail_lines__unioned) with the rules pipeline/ELT.md's "What wave
-- 1's live reads found that phase C must honour" gives trail lines, read
-- from the layer_rules seed, where each row quotes the evidence it rests on.
-- No mart reads this yet; every layer here is held back by its sources.json
-- row (`reaches_hikers: false`), and the routable network
-- (int_trail_lines__network_*) does not read these layers.
--
-- THE RULES, each a unit test in _trail_lines__club_lines.yml:
-- - A HISTORIC ALIGNMENT IS NOT TREAD. A layer the seed marks
--   `historic_alignment` (NPS's National Historic Trail lines, OCTA's atlas
--   routes: ruts, swales, congressional, driving and water routes, much of
--   them on private land and roads) has may_route and draws_as_trail false
--   on every line: never drawn as a trail a hiker can walk, never joined to
--   the routable network.
-- - A WINTER TRAIL IS SEASONAL. A layer the seed marks `winter_trail` (BLM's
--   Iditarod line, "primarily a winter trail") carries season 'winter' on
--   every line, which a drawing must show before it draws the line at all.
-- - ROADS RIDE IN SOME TRAIL LAYERS. A `drop_where` row leaves out every
--   line whose field (dlt's name, read from `properties`) equals its value:
--   MassGIS DCR's roads-and-trails layer loses its TYPE 'Public Road' lines.
--   A filter, so it lives here and not in staging (decision 40).
-- - TWO DIMENSIONS. geom_wkt is ST_Force2D of the line, so a Z-enabled
--   layer's heights (ATA's Z is feet, ATC's metres) never ride into a
--   network built from it; had_z says which lines arrived with one.
with unioned as (
    select * from {{ ref('int_trail_lines__unioned') }}
),

rules as (
    select * from {{ ref('layer_rules') }}
),

layer_flags as (
    select
        source_key,
        bool_or(rule = 'historic_alignment') as historic_alignment,
        bool_or(rule = 'winter_trail') as winter_trail
    from rules
    where field is null
    group by source_key
),

dropped as (
    select distinct unioned.trail_segment_key
    from unioned
    inner join rules
        on
            unioned.source_key = rules.source_key
            and rules.rule = 'drop_where'
            and json_extract_string(unioned.properties, '$.' || rules.field)
            = rules.matches
)

select
    unioned.trail_segment_key,
    unioned.source_key,
    unioned.club,
    unioned.name,
    st_astext(st_force2d(unioned.geom)) as geom_wkt,
    coalesce(st_hasz(unioned.geom), false) as had_z,
    coalesce(layer_flags.historic_alignment, false) as historic_alignment,
    not coalesce(layer_flags.historic_alignment, false) as may_route,
    not coalesce(layer_flags.historic_alignment, false) as draws_as_trail,
    case when layer_flags.winter_trail then 'winter' end as season,
    unioned._loaded_at
from unioned
left join layer_flags on unioned.source_key = layer_flags.source_key
where
    unioned.trail_segment_key not in (
        select dropped.trail_segment_key from dropped
    )
