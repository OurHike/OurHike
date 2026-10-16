{{ config(materialized='table') }}
-- Every line of the clubs' registered trail-line layers (the wave
-- 1, int_trail_lines__unioned) with the rules pipeline/ELT.md's "What wave
-- 1's live reads found that phase C must honour" gives trail lines, read
-- from the layer_rules seed, where each row quotes the evidence it rests on.
-- int_trail_lines__club_published draws what may draw, only
-- where its source may publish, and the routable network
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
--   A filter, so it lives here and not in staging.
-- - A STATUS LAYER DRAWS ONLY WHAT IT CALLS TRAIL. `keep_only_where` rows
--   leave out every line whose field is none of their values, compared
--   without case or surrounding space as the point rules compare
--   (int_points_of_interest__club_points), and a line with no value is left
--   out too: omit rather than guess. NGPC's Cowboy Trail sections draw only
--   where Road_Status is 'Open' or 'Closed' (the maintainer's P8, wave 6's
--   review page 01, 2026-10-11: the developed trail only), so its two 'Alt
--   Route' sections, the HWY 275 detour beside the closed Elkhorn bridges,
--   never draw as trail, nor does a value NGPC adds later.
-- - A LINE ITS OWN LAYER CLOSES IS CLOSED. `closed_where` rows mark a line
--   whose field equals one of their values, compared the same way,
--   `closed_by_its_layer`: int_trail_lines__club_published ships it closed,
--   as a steward's closure on a network line ships. NGPC's sections close on
--   Road_Status 'Closed' or Condition 'Impassable' or 'Not Passable',
--   whatever the other reads, the values the shared vocabulary
--   (seeds/notice_words.csv) reads as closing the trail for
--   its notices (tests/test_ngpc_cowboy_trail.py holds the two alike): 3 of its
--   29 sections on the live read of 2026-10-11, the Niobrara bridge's,
--   'Open' beside 'Not Passable', among them.
-- - TWO DIMENSIONS. geom_wkt is ST_Force2D of the line, so a Z-enabled
--   layer's heights (ATA's Z is feet, ATC's metres) never ride into a
--   network built from it; had_z says which lines arrived with one.
-- - A TRAIL LINE IS A LINE. A GIS file mixes kinds (the wave 2:
--   OTA's My Map carries 72 trailheads beside its 89 lines, Condor's KMLs 2
--   polygons, the Nez Perce NHT's map 110 tour stops), so a row whose
--   geometry is not a LINESTRING or MULTILINESTRING is left out here; its
--   points reach the POI branch through their own file. A row with no
--   geometry is kept, as before.
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
),

-- Each line's value of each field a keep_only_where or closed_where row on
-- its layer names, trimmed and folded.
rule_reads as (
    select
        unioned.trail_segment_key,
        rules.rule,
        rules.field,
        lower(trim(rules.matches)) as matches_folded,
        lower(
            trim(json_extract_string(unioned.properties, '$.' || rules.field))
        ) as value_folded
    from unioned
    inner join rules
        on
            unioned.source_key = rules.source_key
            and rules.rule in ('keep_only_where', 'closed_where')
),

not_kept as (
    select trail_segment_key
    from rule_reads
    where rule = 'keep_only_where'
    group by trail_segment_key, field
    having not coalesce(bool_or(value_folded = matches_folded), false)
),

closed as (
    select distinct trail_segment_key
    from rule_reads
    where rule = 'closed_where' and value_folded = matches_folded
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
    unioned.trail_segment_key in (
        select closed.trail_segment_key from closed
    ) as closed_by_its_layer,
    unioned._loaded_at
from unioned
left join layer_flags on unioned.source_key = layer_flags.source_key
where
    unioned.trail_segment_key not in (
        select dropped.trail_segment_key from dropped
    )
    and unioned.trail_segment_key not in (
        select not_kept.trail_segment_key from not_kept
    )
    and (
        unioned.geom is null
        or st_geometrytype(unioned.geom) in ('LINESTRING', 'MULTILINESTRING')
    )
