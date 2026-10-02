-- The junction graph a day hike routes over, one row per edge (pipeline/
-- ELT.md, "The eleven marts"): a piece of a maintained trail line between
-- two junctions, as build_trail_graph.py builds it today, in the order
-- trail_graph.json lists the edges. Keyed by edge_id; edge_index is the
-- position every companion file is aligned by.
--
-- PUBLICATION is the trail_lines mart's, upstream of the noding: only lines
-- whose source may publish reach the graph at all. It cannot be applied
-- here, because noding is global: dropping an edge after the edges are
-- numbered would shift every later edge_index and misalign every companion
-- file (trail_graph_geometry.json, trail_graph_elevation.json,
-- trail_graph_profile.json).
-- assert_every_graph_edge_comes_from_a_source_that_may_publish holds it.
--
-- No closed trail is an edge (TN01, a safety field of ELT.md's table):
-- assert_no_closed_trail_is_a_graph_edge. "Closed" means closures known at
-- the monthly build; a closure that starts later reaches routing only when
-- the client applies the hourly `closures`. Today's manually dispatched
-- graph has the same gap; it is flagged here, not fixed.
select
    edge_id,
    edge_index,
    club,
    source_key,
    _loaded_at,
    trail_id,
    name,
    blaze_color,
    from_node,
    to_node,
    length_m,
    geom_geojson
from {{ ref('int_trail_network__edges') }}
