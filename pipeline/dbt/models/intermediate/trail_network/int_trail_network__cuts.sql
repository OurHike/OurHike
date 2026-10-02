{{ config(materialized='table') }}
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
--   vertical, horizontal and zero-length ones among them.
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
with parts as (
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

-- The pairs whose envelopes meet, each once. The inequality is applied
-- outside the join so DuckDB plans the envelope test as a spatial join.
touching_boxes as (
    select
        lower_box.part_order as low_order,
        higher_box.part_order as high_order
    from parts as lower_box
    inner join parts as higher_box
        on st_intersects(
            st_envelope(lower_box.geom_m), st_envelope(higher_box.geom_m)
        )
),

candidates as (
    select
        touching_boxes.low_order,
        touching_boxes.high_order,
        low_part.part_id as low_part_id,
        high_part.part_id as high_part_id,
        low_part.geom_m as low_m,
        high_part.geom_m as high_m,
        st_intersects(low_part.geom_m, high_part.geom_m) as crosses
    from touching_boxes
    inner join parts as low_part
        on touching_boxes.low_order = low_part.part_order
    inner join parts as high_part
        on touching_boxes.high_order = high_part.part_order
    where touching_boxes.low_order < touching_boxes.high_order
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
    from candidates
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
        st_distance_geos(st_startpoint(low_m), high_m) as end_distance_m,
        st_astext(st_startpoint(low_m)) as end_point_wkt
    from candidates
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
        st_distance_geos(st_endpoint(low_m), high_m) as end_distance_m,
        st_astext(st_endpoint(low_m)) as end_point_wkt
    from candidates
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
        st_distance_geos(st_startpoint(high_m), low_m) as end_distance_m,
        st_astext(st_startpoint(high_m)) as end_point_wkt
    from candidates
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
        st_distance_geos(st_endpoint(high_m), low_m) as end_distance_m,
        st_astext(st_endpoint(high_m)) as end_point_wkt
    from candidates
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
