-- TN01, a safety field of pipeline/ELT.md's table: no edge of the junction
-- graph runs on a line the trail_lines mart marks closed, long-term by its
-- steward or inside one of NYS Parks' closed areas. A router that paths down
-- a trail its steward closed is FEATURES.md's confidently-wrong answer, on
-- the one screen a hiker uses to decide where to walk
-- (build_trail_graph.py's header). Returns one row per such edge.
select
    edges.edge_id,
    trail_line.trail_line_id,
    trail_line.trail_status
from {{ ref('trail_network') }} as edges
inner join {{ ref('trail_lines') }} as trail_line
    on edges.trail_id = trail_line.trail_line_id
where lower(coalesce(trail_line.trail_status, '')) = 'closed'
