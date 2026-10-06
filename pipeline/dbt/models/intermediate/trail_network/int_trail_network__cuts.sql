{{ config(materialized='table', tags=['builds_alone']) }}
-- builds_alone: Out of Memory Error here in monthly run 20 (37296900535).
-- Run 21 (37323395441) built it alone and ran out again: see "ONE PIECE AT A
-- TIME".
{%- set snap_m = var('trail_network_endpoint_snap_m') %}
{%- set piece_segments = var('trail_network_piece_segments') %}
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
-- ONE PIECE AT A TIME. Each routable part is tested against the others a
-- piece at a time: consecutive runs of at most trail_network_piece_segments
-- segments (dbt_project.yml), each sharing its end vertex with the next, so
-- the pieces hold exactly the part's own segments. Two parts cross when a
-- piece of one meets a piece of the other, and an end lies within
-- trail_network_endpoint_snap_m of a part when it lies that close to one of
-- its pieces. Both are what testing the whole lines answers (Reasoned: a
-- line meets another exactly where one of its segments meets one of the
-- other's, and GEOS's distance from a point to a line is its least distance
-- to any one segment), and the pair rule stays node_lines()': only parts
-- whose envelopes meet, a crossing pair never also joined.
--
-- WHY, measured in three monthly runs and on the published network, each
-- building this model alone against DuckDB's 12.4 GiB:
-- - monthly run 21 (refresh-reference.yml 37323395441, 2026-10-05) held
--   both parts' geometries on every pair whose envelopes meet, in a CTE five
--   others read: out of memory after 34.74 s;
-- - monthly run 22 (37370582492, 2026-10-05; 461954c4) worked each pair's
--   facts out inside the spatial join, which then carried every part's
--   whole geometry on each match: out of memory after 9.31 s;
-- - holding only envelopes in the spatial join (de8fe591) fitted, but slowly:
--   on UA's nearby_trails.geojson (read 2026-10-06; 368,544 parts, 17.2
--   million vertices, its lines simplified for phones), 3.60 GiB and 1,678.7
--   s on DuckDB 1.5.5 with 4 threads, and 23.2 s with the 29 parts of more
--   than 10,000 vertices left out. Those 29 parts were nearly all the time:
--   a part of 265,802 vertices meets the envelope of every part near any of
--   its length, and each such pair tested the whole of it. The lines this
--   model reads are not simplified, so they are longer still.
-- A piece's envelope is near only what is near that piece, and no single
-- test reads more than one piece.
--
-- `parts` is read where each use needs it, never held as a table: DuckDB
-- would otherwise materialize a whole copy of every geometry.
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

-- What each part brings to a cut: its id, its envelope for node_lines()'
-- pair rule, and its two ends as WKT. ST_AsText wrote a 5070 point that
-- reads back as the same two doubles (the header), so `end_point_wkt` is
-- the end shapely welds.
part_info as (
    select
        part_order,
        part_id,
        st_envelope(geom_m) as envelope_m,
        st_astext(st_startpoint(geom_m)) as start_wkt,
        st_astext(st_endpoint(geom_m)) as end_wkt
    from parts
),

-- Piece n of a part holds its vertices n * piece_segments + 1 to
-- (n + 1) * piece_segments + 1, counted from 1, so each piece ends on the
-- vertex the next begins on, and a part of v vertices has
-- (v - 2) // piece_segments + 1 pieces. Built from each part's own list of
-- vertices. A row per vertex, ordered back into lines, held every vertex of
-- the network at once: on the synthetic network below it ran out of memory
-- at 9.3 GiB (measured 2026-10-06).
pieces as (
    select
        part_order,
        unnest(
            list_transform(
                range((len(vertices) - 2) // {{ piece_segments }} + 1),
                lambda piece_index: st_makeline(
                    list_slice(
                        vertices,
                        piece_index * {{ piece_segments }} + 1,
                        piece_index * {{ piece_segments }}
                        + {{ piece_segments }} + 1
                    )
                )
            )
        ) as piece
    from (
        select
            part_order,
            list_transform(
                st_dump(st_points(geom_m)),
                lambda vertex: struct_extract(vertex, 'geom')
            ) as vertices
        from parts
    ) as listed
),

-- The pairs that cross: a piece of the lower part meets a piece of the
-- higher. WHY sign(): written `lower < higher`, DuckDB 1.5.4 planned the
-- inequality as the join (PIECEWISE_MERGE_JOIN) and the spatial test as a
-- filter on all 1,181,953 pairs of 1,538 real Harriman parts, 5.2 s that
-- grows as the square of the parts, in every placement tried. As sign() of
-- the difference it is no join condition, and the spatial test plans as a
-- SPATIAL_JOIN, 0.3 s (EXPLAIN and timings measured 2026-10-02 on DuckDB
-- 1.5.4 with spatial 28db190). Two parts that cross have envelopes that
-- meet, so node_lines()' pair rule needs no test here.
crossing_pairs as (
    select distinct
        lower_piece.part_order as low_order,
        higher_piece.part_order as high_order
    from pieces as lower_piece
    inner join pieces as higher_piece
        on st_intersects(lower_piece.piece, higher_piece.piece)
    where sign(higher_piece.part_order - lower_piece.part_order) = 1
),

crossings as (
    select
        crossing_pairs.low_order,
        crossing_pairs.high_order,
        0 as direction,
        0 as end_rank,
        'crossing' as cut_kind,
        low_info.part_id as line_part_id,
        high_info.part_id as other_part_id,
        cast(null as varchar) as end_side,
        cast(null as varchar) as end_point_wkt
    from crossing_pairs
    inner join part_info as low_info
        on crossing_pairs.low_order = low_info.part_order
    inner join part_info as high_info
        on crossing_pairs.high_order = high_info.part_order
),

-- Each part's two ends, start first.
part_ends as (
    select
        part_order,
        0 as end_rank,
        st_startpoint(geom_m) as end_m
    from parts
    union all
    select
        part_order,
        1 as end_rank,
        st_endpoint(geom_m) as end_m
    from parts
),

-- Each end within the tolerance of another part, by ST_Distance_GEOS to one
-- of its pieces. ST_DWithin plans the spatial join and is DuckDB's own
-- distance, which differed from GEOS's in the last bits (the header), so it
-- only narrows, at a millimetre more than the tolerance; GEOS decides.
-- "Another part" is sign() for the reason crossing_pairs gives: written
-- `!=`, DuckDB 1.5.5 planned it as a NESTED_LOOP_JOIN, 310.9 s against
-- 33,000 synthetic lines (measured 2026-10-06).
near_ends as (
    select distinct
        part_ends.part_order as line_order,
        part_ends.end_rank,
        pieces.part_order as other_order
    from part_ends
    inner join pieces
        on st_dwithin(part_ends.end_m, pieces.piece, {{ snap_m }} + 0.001)
    where
        {{ snap_m }} > 0
        and sign(pieces.part_order - part_ends.part_order) != 0
        and st_distance_geos(part_ends.end_m, pieces.piece) <= {{ snap_m }}
),

-- An end joins the part it lies near when their envelopes meet and the two
-- do not cross: the lower part's ends against the higher are direction 0,
-- the higher's against the lower direction 1.
joins as (
    select
        least(near_ends.line_order, near_ends.other_order) as low_order,
        greatest(near_ends.line_order, near_ends.other_order) as high_order,
        case
            when near_ends.line_order < near_ends.other_order then 0 else 1
        end as direction,
        near_ends.end_rank,
        'endpoint_join' as cut_kind,
        line_info.part_id as line_part_id,
        other_info.part_id as other_part_id,
        case near_ends.end_rank when 0 then 'start' else 'end' end as end_side,
        case near_ends.end_rank
            when 0 then line_info.start_wkt
            else line_info.end_wkt
        end as end_point_wkt
    from near_ends
    inner join part_info as line_info
        on near_ends.line_order = line_info.part_order
    inner join part_info as other_info
        on near_ends.other_order = other_info.part_order
    left join crossing_pairs
        on
            least(near_ends.line_order, near_ends.other_order)
            = crossing_pairs.low_order
            and greatest(near_ends.line_order, near_ends.other_order)
            = crossing_pairs.high_order
    where
        crossing_pairs.low_order is null
        and st_intersects(line_info.envelope_m, other_info.envelope_m)
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
