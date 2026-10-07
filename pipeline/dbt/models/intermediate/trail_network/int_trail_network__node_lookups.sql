{{ config(materialized='table') }}
{%- set quant_m = var('trail_network_node_quant_m') %}
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
-- WHY IT SETTLES IN ROUNDS. Whether a point makes a node depends on
-- whether an earlier point near it made one, so the grid is sequential:
-- three ends 0.4 m apart in a row make two nodes, not one, because the
-- third is 0.8 m from the first. Each round settles every point whose
-- earlier neighbours are all settled: one that has a node-making neighbour
-- finds a node, one whose neighbours all found theirs makes its own. Which
-- node a point finds is decided only once every point is settled.
--
-- The rounds run in two parts. The first trail_network_node_rounds (8)
-- run over every point, each a join of the whole network. The rest run
-- over only the points those left unsettled and their neighbours,
-- `tail_rounds`, a recursive CTE whose every round carries that small set's
-- whole state and how many of it are still open; the round after the first
-- with none open is empty, which ends it. It always ends: the lowest
-- unsettled point's earlier neighbours are all settled, so every round
-- settles at least that one.
--
-- The rest used not to exist. Monthly run 24 (refresh-reference.yml
-- 37459433469, 2026-10-06) built 3,556,603 pieces, 373 of whose points
-- were still unsettled after the eighth round, and the `not_null` on
-- `node_raw` stopped the build. The k-th of a row of ends 0.3 m apart
-- settles in round k (unit test
-- int_trail_network__node_lookups_a_long_row_of_ends_settles), so no fixed
-- count is safe. Which points were left the run did not say; two
-- near-coincident lines crossing every few decimetres would make such a
-- row (Reasoned, not traced). `node_raw` keeps its `not_null` as a guard.
--
-- Why not every round as a recursion over the whole network: DuckDB's
-- `with recursive ... using key` can keep one row per point, but each of
-- its rounds then reads the whole table, and on a synthetic network of the
-- real one's size (3,718,000 pieces, 300 rows of 60 ends 0.3 m apart;
-- DuckDB 1.5.5, 4 threads, measured 2026-10-07 in the sandbox) it ran past
-- 5 minutes and was stopped, where 8 rounds over everything took 33.6 s and
-- left 15,300 points. `using key` is also a clause dbt 2.0.6's `dbt lint`
-- refuses as a syntax error, and SQLFluff 4.3.0 cannot parse it, so the
-- tail is plain `with recursive`. On the same synthetic network the two
-- parts took 41.0 s and settled every one of the 7,436,000 points, each
-- with build_trail_graph._node_id()'s answer.
--
-- `node_raw` is the node's number in _node_id()'s `points`, before the
-- welds merge any (int_trail_network__raw_edges). A weld's point that makes
-- a node of its own is the one place the cut order reaches the graph
-- (int_trail_network__cuts says why its order is not STRtree's): `makes_node`
-- on a weld row says so, and the warn test on it names any.
--
-- Squares are pow(x, 2), the C library's pow(), which Python's `** 2` on a
-- float also calls.
with recursive pieces as (
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
        cast(floor(x / {{ quant_m }}) as bigint) as cell_x,
        cast(floor(y / {{ quant_m }}) as bigint) as cell_y
    from lookups
),

offsets as (
    select unnest([-1, 0, 1]) as step
),

-- Each point's nine cells, the scan's 3 x 3, as plain columns: with the
-- offset added inside the join instead, DuckDB 1.5.4 planned `seq < seq`
-- as the join and the cells as a filter on its 2,862,104,310 rows, 349 s on
-- 25,220 points of real Harriman lines (measured 2026-10-02); keyed like
-- this the cells are a hash join.
probes as materialized (
    select
        cells.seq,
        cells.x,
        cells.y,
        across.step as dx,
        up.step as dy,
        cells.cell_x + across.step as near_cell_x,
        cells.cell_y + up.step as near_cell_y
    from cells
    cross join offsets as across
    cross join offsets as up
),

-- Every earlier point within the grid's reach of each point, with the cell
-- offset the scan meets it at.
neighbours as materialized (
    select
        probes.seq,
        near.seq as near_seq,
        probes.dx,
        probes.dy
    from probes
    inner join cells as near
        on
            probes.near_cell_x = near.cell_x
            and probes.near_cell_y = near.cell_y
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
-- The points the first rounds left unsettled, each with its neighbours.
tail_neighbours as materialized (
    select
        neighbours.seq,
        neighbours.near_seq
    from neighbours
    inner join status_{{ rounds }} as own on neighbours.seq = own.seq
    where own.status is null
),

-- Which rows of a round each tail point reads: its own, and each
-- neighbour's.
tail_reads as materialized (
    select distinct
        tail_point.seq,
        tail_point.seq as read_seq,
        true as is_own
    from (
        select seq from tail_neighbours
        union distinct
        select near_seq as seq from tail_neighbours
    ) as tail_point
    union all
    select
        tail_neighbours.seq,
        tail_neighbours.near_seq as read_seq,
        false as is_own
    from tail_neighbours
),

-- The rest of the rounds, on those points alone. Each round is every tail
-- point's status, with how many are still open; the round after the first
-- with none open is empty, which ends the recursion.
tail_rounds as (
    select
        0 as tail_round,
        after_rounds.seq,
        after_rounds.status,
        sum(case when after_rounds.status is null then 1 else 0 end) over ()
            as still_open
    from status_{{ rounds }} as after_rounds
    where after_rounds.seq in (select tail_reads.seq from tail_reads)
    union all
    select
        next_round.tail_round,
        next_round.seq,
        next_round.status,
        sum(case when next_round.status is null then 1 else 0 end) over ()
            as still_open
    from (
        select
            tail_reads.seq,
            max(last_round.tail_round) + 1 as tail_round,
            coalesce(
                max(case when tail_reads.is_own then last_round.status end),
                case
                    when
                        bool_or(
                            case
                                when not tail_reads.is_own
                                    then last_round.status = 'makes'
                            end
                        )
                        then 'finds'
                    when
                        bool_and(
                            case
                                when not tail_reads.is_own
                                    then last_round.status is not null
                            end
                        )
                        then 'makes'
                end
            ) as status
        from tail_rounds as last_round
        inner join tail_reads on last_round.seq = tail_reads.read_seq
        where last_round.still_open > 0
        group by tail_reads.seq
    ) as next_round
),

settled_tail as (
    select
        tail_rounds.seq,
        tail_rounds.status
    from tail_rounds
    where
        tail_rounds.tail_round
        = (select max(every_round.tail_round) from tail_rounds as every_round)
),

settled as (
    select
        after_rounds.seq,
        coalesce(after_rounds.status, settled_tail.status) as status
    from status_{{ rounds }} as after_rounds
    left join settled_tail on after_rounds.seq = settled_tail.seq
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
    coalesce(
        own_node.node_raw,
        case when settled.status = 'finds' then found.node_raw end
    ) as node_raw
from cells
inner join settled on cells.seq = settled.seq
left join makers as own_node on cells.seq = own_node.seq
left join found on cells.seq = found.seq
