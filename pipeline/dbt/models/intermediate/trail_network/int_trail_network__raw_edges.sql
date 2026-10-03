{{ config(materialized='table') }}
{%- set quant_m = var('trail_network_node_quant_m') %}
-- Every piece build_graph() keeps as an edge before it compacts the nodes,
-- with the node each end becomes once the welds have merged nodes, and
-- whether compaction then drops it (build_trail_graph.py, TN06's rest):
--
-- - A piece whose two ends found one node and whose length is at most
--   trail_network_node_quant_m (0.5 m) is a loop shorter than the grid, float
--   noise rather than a walkable circuit, and is never an edge.
-- - Each weld merges the node of a joined line end with the node of its
--   landing; a merged node is the lowest-numbered of its group, as
--   build_graph()'s union keeps the lower id, so the answer does not depend
--   on the order the welds arrive in.
-- - The published nodes are numbered in the order the kept pieces first
--   reach them, from end then to end, piece by piece, dropped ones too.
-- - A kept piece whose two ends became one node and whose published length
--   (2 decimals) is at most 0.5 m is dropped, its nodes still numbered: the
--   Python numbers both ends before it tests the loop.
--
-- Lengths are EPSG:5070 metres, ST_Length of the piece, which gave shapely's
-- `length` to the bit on 20,000 of 20,000 random lines (measured 2026-10-02
-- on DuckDB 1.5.4 with spatial 28db190). `length_m` is that rounded to 2
-- decimals as Python's round() rounds it (printf, not DuckDB's round()).
with recursive lookups as (
    select * from {{ ref('int_trail_network__node_lookups') }}
),

pieces as (
    select
        piece_starts.piece_rank,
        piece_starts.part_id,
        piece_starts.piece_index,
        piece_starts.node_raw as from_raw,
        finishes.node_raw as to_raw
    from lookups as piece_starts
    inner join lookups as finishes
        on
            piece_starts.piece_rank = finishes.piece_rank
            and finishes.lookup_kind = 'piece_end'
    where piece_starts.lookup_kind = 'piece_start'
),

measured as (
    select
        pieces.*,
        st_length(graph_pieces.geom) as length_raw_m,
        st_astext(graph_pieces.geom) as geom_m_wkt
    from pieces
    inner join {{ ref('stg_derived__graph_pieces') }} as graph_pieces
        on
            graph_pieces.row_kind = 'piece'
            and pieces.part_id = graph_pieces.part_id
            and pieces.piece_index = graph_pieces.piece_index
),

kept as (
    select
        *,
        row_number() over (order by piece_rank) - 1 as edge_rank
    from measured
    where not (from_raw = to_raw and length_raw_m <= {{ quant_m }})
),

weld_pairs as (
    select
        ends.node_raw as end_node,
        landings.node_raw as landing_node
    from lookups as ends
    inner join lookups as landings
        on
            ends.cut_key = landings.cut_key
            and landings.lookup_kind = 'weld_landing'
    where ends.lookup_kind = 'weld_end'
),

weld_links as (
    select
        end_node as node_a,
        landing_node as node_b
    from weld_pairs
    union all
    select
        landing_node as node_a,
        end_node as node_b
    from weld_pairs
),

-- Each welded node's group, as the lowest node that reaches it: a walk from
-- every node to the higher ones it links to, so the group's lowest reaches
-- all of it.
reach (node_raw, label) as (
    select
        node_a as node_raw,
        node_a as label
    from weld_links
    union distinct
    select
        weld_links.node_b as node_raw,
        reach.label
    from reach
    inner join weld_links on reach.node_raw = weld_links.node_a
    where weld_links.node_b > reach.label
),

roots as (
    select
        node_raw,
        min(label) as root_raw
    from reach
    group by node_raw
),

rooted as (
    select
        kept.*,
        coalesce(from_root.root_raw, kept.from_raw) as from_root,
        coalesce(to_root.root_raw, kept.to_raw) as to_root
    from kept
    left join roots as from_root on kept.from_raw = from_root.node_raw
    left join roots as to_root on kept.to_raw = to_root.node_raw
),

appearances as (
    select
        from_root as root_raw,
        edge_rank * 2 as reached_at
    from rooted
    union all
    select
        to_root as root_raw,
        edge_rank * 2 + 1 as reached_at
    from rooted
),

numbered as (
    select
        root_raw,
        row_number() over (order by min(reached_at)) - 1 as node_index
    from appearances
    group by root_raw
),

published as (
    select
        rooted.*,
        from_number.node_index as from_node,
        to_number.node_index as to_node,
        cast(printf('%.2f', rooted.length_raw_m) as double) as length_m
    from rooted
    inner join numbered as from_number
        on rooted.from_root = from_number.root_raw
    inner join numbered as to_number
        on rooted.to_root = to_number.root_raw
)

select
    edge_rank,
    piece_rank,
    part_id,
    piece_index,
    from_raw,
    to_raw,
    from_root,
    to_root,
    from_node,
    to_node,
    length_raw_m,
    length_m,
    from_node = to_node and length_m <= {{ quant_m }} as dropped_as_a_loop,
    geom_m_wkt
from published
