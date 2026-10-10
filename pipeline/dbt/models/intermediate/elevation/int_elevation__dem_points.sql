{{ config(materialized='table') }}
-- Every point step_dem_sampling asks the DEM about, in the order today's
-- exporters ask (EL06 of pipeline/ELT.md's ledger): the A.T.'s walk first,
-- every sample of it, then each junction-graph edge by its place in
-- trail_graph.json (edge_index), each edge's samples from its start.
--
-- THE ORDER DECIDES NO ANSWER. Since decision 115 the sampler's cache keys
-- each point on its exact coordinates (export_elevation.SAMPLE_CACHE_KEYS),
-- so every point is answered at its own pixel whoever asked first. Until
-- then a 6-decimal key gave a point the pixel of whichever point within
-- about 0.11 m was asked first, and this order was what made the dbt lane's
-- first asker today's. ask_order stays the order step_dem_sampling reads
-- the rows in, so the same rows ask the same questions in the same order
-- and a cold run writes the same cache file.
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
