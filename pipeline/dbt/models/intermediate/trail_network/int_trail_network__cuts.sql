{{ config(materialized='table', tags=['builds_alone']) }}
-- builds_alone: Out of Memory Error here in monthly run 20 (37296900535).
-- Run 21 (37323395441) built it alone and ran out again: see pair_facts.
{%- set snap_m = var('trail_network_endpoint_snap_m') %}
-- Where the routable lines must be cut, as node_lines() decides it
-- (build_trail_graph.py, TN04's inputs and TN05): one row per pair of parts
-- that cross or touch, and one per line END that stops short of another
-- line. step_node_lines makes the cuts themselves, with shapely, so the
-- pieces are the ones build_trail_graph.py makes to the bit (TN04); this
-- model is which cuts to make.
--
-- EVERY DISTANCE IN EPSG:5070 METRES (always_xy), as build() projects the
-- lines. Measured 2026-10-02 on DuckDB 1.5.4 with spatial 28db190, the
-- engine dbt 2.0.6 runs, against pyproj 3.7.2 (PROJ 9.5.1) and shapely 2.1.2
-- (GEOS 3.13.1):
-- - ST_Transform gave pyproj's doubles on 200,000 of 200,000 random US
--   points, both ways;
-- - ST_Intersects of two lines gave shapely's answer on 4,000 of 4,000
--   pairs built to meet awkwardly (a shared end, an end on the other's
--   interior, a shared vertex, a collinear overlap, a nanometre's miss);
-- - ST_Distance_GEOS from a line's end to another line gave shapely's
--   distance to the bit on all 4,000, where DuckDB's own ST_Distance did on
--   1,158, which is why this model names the GEOS one;
-- - the pairs whose envelopes meet were STRtree.query's on 6,000 lines,
--   vertical, horizontal and zero-length ones among them;
-- - ST_AsText wrote a 5070 point that reads back as the same two doubles
--   on 20,000 of 20,000, so `end_point_wkt` is the end shapely welds.
--
-- THE TWO WAYS TWO TRAILS MEET, the module's design decision:
-- 1. lines that cross or touch are cut exactly where they meet, with no
--    tolerance (`crossing`, one row per pair, the lower part first, as
--    node_lines() asks `line.intersects(other)` of each pair whose envelopes
--    meet);
-- 2. an END of one line within trail_network_endpoint_snap_m (8 m,
--    @unvalidated: build_trail_graph.py --sweep against real layers settles
--    it) of another line it does NOT cross is joined to it (`endpoint_join`):
--    the other line is cut where the end comes closest, and the two become
--    one node. Only an end: a parallel trail 30 m away for two miles has no
--    end in that corridor, so no tolerance short of absurd welds it on. A
--    pair that crosses is never also joined, as the Python `continue`s.
-- Both kinds look only at pairs whose envelopes meet, the candidates
-- STRtree.query hands node_lines(), so an end within 8 m of a line whose
-- envelope its own does not meet is not joined there either: rounding
-- toward disconnection, the safe direction (a missed junction is a refusal
-- a hiker can act on; an invented one is a route across ground with no
-- trail).
--
-- `cut_order` is node_lines()' loop order where SQL can follow it: the lower
-- part, then the higher, then the lower part's two ends against the higher
-- and the higher's against the lower, each start before end. STRtree hands
-- the higher parts in tree order, not in this one; the order reaches the
-- graph only where a weld creates a node of its own
-- (int_trail_network__node_lookups says when).
-- Read where each use needs it, never held as a table: three uses read it,
-- and DuckDB would otherwise materialize a whole copy of every geometry
-- ("WHERE THE MEMORY GOES" below).
with parts as not materialized (
    select
        part_id,
        part_order,
        st_transform(
            st_geomfromtext(geom_wkt), 'EPSG:4326', 'EPSG:5070',
            always_xy := true
        ) as geom_m
    from {{ ref('int_trail_network__routable') }}
    where refused_because is null
),

-- Each part's envelope, the only thing the spatial join holds.
boxes as (
    select
        part_order,
        st_envelope(geom_m) as envelope_m
    from parts
),

-- The pairs whose envelopes meet, each once, the lower part first. WHY
-- sign(): written `lower < higher`, DuckDB 1.5.4 planned the inequality as
-- the join (PIECEWISE_MERGE_JOIN) and the envelope test as a filter on all
-- 1,181,953 pairs of 1,538 real Harriman parts, 5.2 s that grows as the
-- square of the parts, in every placement tried: in the WHERE, in the ON,
-- outside a materialized CTE. As sign() of the difference it is no join
-- condition, and the envelope test plans as a SPATIAL_JOIN, 0.3 s (EXPLAIN
-- and timings measured 2026-10-02 on DuckDB 1.5.4 with spatial 28db190).
touching_boxes as (
    select
        lower_box.part_order as low_order,
        higher_box.part_order as high_order
    from boxes as lower_box
    inner join boxes as higher_box
        on st_intersects(lower_box.envelope_m, higher_box.envelope_m)
    where sign(higher_box.part_order - lower_box.part_order) = 1
),

-- WHERE THE MEMORY GOES, measured in two monthly runs on 332,630 network
-- lines (refresh-reference.yml run 37323395441, monthly run 21, and run
-- 37370582492, monthly run 22, 2026-10-05), each building this model alone
-- against DuckDB's 12.4 GiB:
-- - run 21's query held both parts' geometries on every touching pair, in a
--   CTE five others read, so DuckDB materialized it: memory that grows with
--   the pairs times their vertices. It ran out after 34.74 s;
-- - run 22's (461954c4) worked every fact out inside the spatial join's own
--   projection, so the join carried every part's whole geometry on its
--   build side, the side it indexes in memory. It ran out after 9.31 s.
-- Here the spatial join holds envelopes and part numbers only, as run 21's
-- did; each pair's two geometries come in through ordinary joins on
-- part_order, which DuckDB can spill to disk; every fact is worked out in
-- the one projection that reads them; and only the scalar facts of the
-- pairs that cut something are kept. Which operator ran out in each run is
-- Reasoned from the two plans and the times, not measured: no synthetic
-- network made either query fail (the synthetic figures are in the commit
-- that made this change). A third failure at this model would settle that
-- this is the wrong side of the problem; the step that cuts the lines,
-- step_node_lines, already holds every part in shapely, which is where the
-- cut list would move.
pair_facts as (
    select
        low_order,
        high_order,
        low_part_id,
        high_part_id,
        crosses,
        low_start_m,
        low_end_m,
        high_start_m,
        high_end_m,
        case
            when low_start_m <= {{ snap_m }}
                then st_astext(st_startpoint(low_m))
        end as low_start_wkt,
        case
            when low_end_m <= {{ snap_m }}
                then st_astext(st_endpoint(low_m))
        end as low_end_wkt,
        case
            when high_start_m <= {{ snap_m }}
                then st_astext(st_startpoint(high_m))
        end as high_start_wkt,
        case
            when high_end_m <= {{ snap_m }}
                then st_astext(st_endpoint(high_m))
        end as high_end_wkt
    from (
        -- An end's distance only for a pair that does not cross: a pair
        -- that crosses is never also joined, as the Python `continue`s.
        select
            *,
            case
                when not crosses
                    then st_distance_geos(st_startpoint(low_m), high_m)
            end as low_start_m,
            case
                when not crosses
                    then st_distance_geos(st_endpoint(low_m), high_m)
            end as low_end_m,
            case
                when not crosses
                    then st_distance_geos(st_startpoint(high_m), low_m)
            end as high_start_m,
            case
                when not crosses
                    then st_distance_geos(st_endpoint(high_m), low_m)
            end as high_end_m
        from (
            select
                lower_part.part_order as low_order,
                higher_part.part_order as high_order,
                lower_part.part_id as low_part_id,
                higher_part.part_id as high_part_id,
                lower_part.geom_m as low_m,
                higher_part.geom_m as high_m,
                st_intersects(lower_part.geom_m, higher_part.geom_m) as crosses
            from touching_boxes
            inner join parts as lower_part
                on touching_boxes.low_order = lower_part.part_order
            inner join parts as higher_part
                on touching_boxes.high_order = higher_part.part_order
        ) as touching
    ) as measured
    where
        crosses
        or ({{ snap_m }} > 0 and low_start_m <= {{ snap_m }})
        or ({{ snap_m }} > 0 and low_end_m <= {{ snap_m }})
        or ({{ snap_m }} > 0 and high_start_m <= {{ snap_m }})
        or ({{ snap_m }} > 0 and high_end_m <= {{ snap_m }})
),

crossings as (
    select
        low_order,
        high_order,
        0 as direction,
        0 as end_rank,
        'crossing' as cut_kind,
        low_part_id as line_part_id,
        high_part_id as other_part_id,
        cast(null as varchar) as end_side,
        cast(null as varchar) as end_point_wkt
    from pair_facts
    where crosses
),

-- Each non-crossing pair's four ends: the lower part's against the higher
-- part (direction 0), then the higher's against the lower (1), start first.
ends as (
    select
        low_order,
        high_order,
        0 as direction,
        0 as end_rank,
        low_part_id as line_part_id,
        high_part_id as other_part_id,
        'start' as end_side,
        low_start_m as end_distance_m,
        low_start_wkt as end_point_wkt
    from pair_facts
    where not crosses
    union all
    select
        low_order,
        high_order,
        0 as direction,
        1 as end_rank,
        low_part_id as line_part_id,
        high_part_id as other_part_id,
        'end' as end_side,
        low_end_m as end_distance_m,
        low_end_wkt as end_point_wkt
    from pair_facts
    where not crosses
    union all
    select
        low_order,
        high_order,
        1 as direction,
        0 as end_rank,
        high_part_id as line_part_id,
        low_part_id as other_part_id,
        'start' as end_side,
        high_start_m as end_distance_m,
        high_start_wkt as end_point_wkt
    from pair_facts
    where not crosses
    union all
    select
        low_order,
        high_order,
        1 as direction,
        1 as end_rank,
        high_part_id as line_part_id,
        low_part_id as other_part_id,
        'end' as end_side,
        high_end_m as end_distance_m,
        high_end_wkt as end_point_wkt
    from pair_facts
    where not crosses
),

joins as (
    select
        low_order,
        high_order,
        direction,
        end_rank,
        'endpoint_join' as cut_kind,
        line_part_id,
        other_part_id,
        end_side,
        end_point_wkt
    from ends
    where {{ snap_m }} > 0 and end_distance_m <= {{ snap_m }}
),

cuts as (
    select * from crossings
    union all
    select * from joins
)

select
    cut_kind || ':' || line_part_id || '|' || other_part_id
    || coalesce('|' || end_side, '') as cut_key,
    row_number() over (
        order by low_order, high_order, direction, end_rank, cut_kind
    ) - 1 as cut_order,
    cut_kind,
    line_part_id,
    other_part_id,
    end_side,
    end_point_wkt
from cuts
