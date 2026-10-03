{{ config(materialized='table') }}
--
-- The junction graph's nodes, which step_form_route reads beside
-- int_trail_network__edges to build the graph lib/trail_graph_route.py
-- routes over: trail_graph.json's `nodes`, one row per node in that list's
-- order, `node_index` its place there (an edge's from_node and to_node), and
-- lon/lat as build_trail_graph.py publishes them, 6 decimals. A node is not
-- always an edge's first or last vertex (build_graph() places it at its
-- quantised cluster's root, and welds merge clusters), so the step cannot
-- read nodes off the edges' geometry: the grid it searches is built from
-- these, and so is the reach of the geometry it keeps.
--
-- The rows pub_trail_graph publishes as `nodes`, from the same
-- int_trail_network__nodes, so a hike is routed over exactly the graph a
-- phone would read. pub_trail_graph's parity against build_trail_graph.py is
-- what holds them to today's: no differences on the fixtures' 172 edges, and
-- byte-identical files over 6,504 and 16,126 nodes cut from live lines (the
-- trail_network family, tl-net, 2026-10-02). Publication is already applied
-- upstream of the noding, in the trail_lines mart, as it is for the file.
select
    node_index,
    lon,
    lat
from {{ ref('int_trail_network__nodes') }}
