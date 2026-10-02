{{ config(materialized='table') }}
{%- set quant_m = var('trail_network_node_quant_m') %}
{#- `| int` and the floor of 1 let SQLFluff, whose var() answers a name,
    render one round; dbt reads the number. -#}
{%- set rounds = [var('trail_network_node_rounds') | int, 1] | max %}
-- Every question build_graph() asks its node grid, in the order it asks
-- them, and the node each answer is (build_trail_graph.py's _node_id(), TN06
-- of pipeline/ELT.md's ledger): each piece's start and end, piece by piece
-- in routable_lines()' part order and step_node_lines' piece order, then the
-- two points of each weld (a joined line end and where it lands), in
-- int_trail_network__cuts' order.
--
-- THE GRID, _node_id()'s own rule, which is first come, first served rather
-- than nearest: a point is an existing node's when that node lies within
-- trail_network_node_quant_m (0.5 m, @unvalidated) of it in real distance,
-- `(dx) ** 2 + (dy) ** 2 <= 0.25`, and the node it is is the first such one
-- the scan meets: the 3 x 3 grid cells of side 0.5 m around the point,
-- west to east and south to north, and in each cell the nodes in the order
-- they were made. A point no node is near makes a new node, numbered in the
-- order the nodes are made. The 3 x 3 cells hold every node within 0.5 m,
-- so the scan misses none (Reasoned: |dx| <= 0.5 puts x / 0.5 within one
-- of the point's, so floor() within one cell).
--
-- WHY ROUNDS. Whether a point makes a node depends on whether an earlier
-- point near it made one, so the grid is sequential: three ends 0.4 m apart
-- in a row make two nodes, not one, because the third is 0.8 m from the
-- first. Each round settles every point whose earlier neighbours are all
-- settled: one that has a node-making neighbour finds a node, one whose
-- neighbours all found theirs makes its own. A cluster of ends at one
-- junction settles in two rounds; trail_network_node_rounds bounds the
-- longest chain, and a point still unsettled after the last fails the
-- build (the `not_null` on `node_raw`) rather than guessing a node. Which
-- node a point finds is decided only once all its neighbours are settled.
--
-- `node_raw` is the node's number in _node_id()'s `points`, before the
-- welds merge any (int_trail_network__raw_edges). A weld's point that makes
-- a node of its own is the one place the cut order reaches the graph
-- (int_trail_network__cuts says why its order is not STRtree's): `makes_node`
-- on a weld row says so, and the warn test on it names any.
--
-- Squares are pow(x, 2), the C library's pow(), which Python's `** 2` on a
-- float also calls.
with pieces as (
    select
        part_id,
        piece_index,
        piece_rank,
        geom
    from {{ ref('stg_derived__graph_pieces') }}
    where row_kind = 'piece'
),

piece_count as (
    select count(*) as pieces from pieces
),

welds as (
    select
        cuts.cut_key,
        row_number() over (order by cuts.cut_order) - 1 as weld_rank,
        st_geomfromtext(cuts.end_point_wkt) as end_point,
        landings.geom as landing_point
    from {{ ref('int_trail_network__cuts') }} as cuts
    inner join {{ ref('stg_derived__graph_pieces') }} as landings
        on
            landings.row_kind = 'landing'
            and cuts.cut_key = landings.cut_key
    where cuts.cut_kind = 'endpoint_join'
),

lookups as (
    select
        piece_rank * 2 as seq,
        'piece_start' as lookup_kind,
        part_id,
        piece_index,
        piece_rank,
        cast(null as varchar) as cut_key,
        st_x(st_startpoint(geom)) as x,
        st_y(st_startpoint(geom)) as y
    from pieces
    union all
    select
        piece_rank * 2 + 1 as seq,
        'piece_end' as lookup_kind,
        part_id,
        piece_index,
        piece_rank,
        cast(null as varchar) as cut_key,
        st_x(st_endpoint(geom)) as x,
        st_y(st_endpoint(geom)) as y
    from pieces
    union all
    select
        piece_count.pieces * 2 + welds.weld_rank * 2 as seq,
        'weld_end' as lookup_kind,
        cast(null as varchar) as part_id,
        cast(null as bigint) as piece_index,
        cast(null as bigint) as piece_rank,
        welds.cut_key,
        st_x(welds.end_point) as x,
        st_y(welds.end_point) as y
    from welds
    cross join piece_count
    union all
    select
        piece_count.pieces * 2 + welds.weld_rank * 2 + 1 as seq,
        'weld_landing' as lookup_kind,
        cast(null as varchar) as part_id,
        cast(null as bigint) as piece_index,
        cast(null as bigint) as piece_rank,
        welds.cut_key,
        st_x(welds.landing_point) as x,
        st_y(welds.landing_point) as y
    from welds
    cross join piece_count
),

cells as (
    select
        *,
        floor(x / {{ quant_m }}) as cell_x,
        floor(y / {{ quant_m }}) as cell_y
    from lookups
),

offsets as (
    select unnest([-1, 0, 1]) as step
),

-- Every earlier point within the grid's reach of each point, with the cell
-- offset the scan meets it at.
neighbours as (
    select
        probes.seq,
        near.seq as near_seq,
        across.step as dx,
        up.step as dy
    from cells as probes
    cross join offsets as across
    cross join offsets as up
    inner join cells as near
        on
            probes.cell_x + across.step = near.cell_x
            and probes.cell_y + up.step = near.cell_y
    where
        near.seq < probes.seq
        and pow(near.x - probes.x, 2) + pow(near.y - probes.y, 2)
        <= cast({{ quant_m }} as double) * cast({{ quant_m }} as double)
),

nearby as (
    select distinct seq from neighbours
),

status_0 as materialized (
    select
        cells.seq,
        case when nearby.seq is null then 'makes' end as status
    from cells
    left join nearby on cells.seq = nearby.seq
),
{% for round in range(1, rounds + 1) %}
status_{{ round }} as materialized (
    select
        own.seq,
        coalesce(
            any_value(own.status),
            case
                when bool_or(near.status = 'makes') then 'finds'
                when bool_and(near.status is not null) then 'makes'
            end
        ) as status
    from status_{{ round - 1 }} as own
    left join neighbours on own.seq = neighbours.seq
    left join status_{{ round - 1 }} as near
        on neighbours.near_seq = near.seq
    group by own.seq
),
{% endfor %}
settled as (
    select * from status_{{ rounds }}
),

makers as (
    select
        settled.seq,
        row_number() over (order by settled.seq) - 1 as node_raw
    from settled
    where settled.status = 'makes'
),

-- The node a point that does not make one finds: the scan's first.
found as (
    select
        neighbours.seq,
        makers.node_raw
    from neighbours
    inner join makers on neighbours.near_seq = makers.seq
    qualify
        row_number() over (
            partition by neighbours.seq
            order by neighbours.dx, neighbours.dy, neighbours.near_seq
        ) = 1
)

select
    cells.seq,
    cells.lookup_kind,
    cells.part_id,
    cells.piece_index,
    cells.piece_rank,
    cells.cut_key,
    cells.x,
    cells.y,
    settled.status,
    settled.status = 'makes' as makes_node,
    coalesce(own_node.node_raw, found.node_raw) as node_raw
from cells
inner join settled on cells.seq = settled.seq
left join makers as own_node on cells.seq = own_node.seq
left join found
    on
        cells.seq = found.seq
        and settled.status = 'finds'
