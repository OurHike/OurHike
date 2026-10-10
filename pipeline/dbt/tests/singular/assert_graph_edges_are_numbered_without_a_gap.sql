-- TN11 and TN12. trail_graph_geometry.json and every companion beside it
-- (trail_graph_elevation.json, trail_graph_profile.json) are aligned to
-- trail_graph.json's `edges` by position alone, so the edges are numbered
-- 0..n-1 with no gap; cut_trail_graph.py refuses a misaligned companion as
-- well. And an empty graph is not published, because an empty family "would
-- read as coverage" (cut_trail_graph.py). Returns a row naming whichever is
-- wrong.
with numbered as (
    select
        count(*) as edges,
        coalesce(max(edge_index), -1) as last_index,
        count(distinct edge_index) as distinct_indexes
    from {{ ref('trail_network') }}
)

select
    edges,
    last_index,
    distinct_indexes,
    case
        when edges = 0 then 'the graph has no edges'
        else 'edge_index is not 0..n-1'
    end as problem
from numbered
where edges = 0 or last_index != edges - 1 or distinct_indexes != edges
