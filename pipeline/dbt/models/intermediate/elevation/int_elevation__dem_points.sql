{{ config(materialized='table') }}
-- Every point step_dem_sampling asks the DEM about, in the order today's
-- exporters ask (EL06 of pipeline/ELT.md's ledger): the A.T.'s walk first,
-- every sample of it, then each junction-graph edge by its place in
-- trail_graph.json (edge_index), each edge's samples from its start.
--
-- WHY THE ORDER IS PART OF THE ANSWER. export_elevation.ElevationSampler
-- answers a second point within 0.11 m of a first with the first's pixel
-- ("whoever asked first", export_elevation.CACHE_KEY_DECIMALS), and the
-- cache beside the tile index carries from one exporter to the next.
-- publish-vector-data.yml runs export_elevation.py, then
-- export_network_elevation.py, which asks for every edge's points in one
-- call in edge order, then export_network_profile.py, which asks for the
-- same points again. So on a cold cache the A.T. is read at its own points,
-- and an edge point that shares an A.T. point's cache key takes the A.T.'s
-- answer; ask_order keeps both true.
--
-- line_id is 'AT' for the A.T. and the edge's edge_id for an edge, and
-- sample_index is the A.T.'s walk position or the edge's own sample index:
-- (line_id, sample_index) is the key derived.dem_samples comes back under.
with lines as (
    select
        line_id,
        sample_index,
        lon,
        lat,
        0 as line_rank,
        0 as line_position
    from {{ ref('int_elevation__sample_points') }}
    union all
    select
        edge_id as line_id,
        sample_index,
        lon,
        lat,
        1 as line_rank,
        edge_index as line_position
    from {{ ref('int_elevation__edge_sample_points') }}
)

select
    line_id,
    sample_index,
    lon,
    lat,
    row_number() over (
        order by line_rank, line_position, sample_index
    ) - 1 as ask_order
from lines
