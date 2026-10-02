-- INTERFACE: replace with tl-net's model
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
-- Zero rows until the trail_network family publishes its nodes (stage 3 of
-- #1793 — Rebuild the data platform as dlt → dbt: seven contracted marts, a
-- monthly refresh, published docs, and lighter phone downloads). With none,
-- every generated hike finds no line within 500 m of its parking and every
-- published track finds no line to re-walk on, so none ships, which is the
-- Python's own answer on an empty graph. It reads the edges only so that it
-- is not a root model.
select
    cast(null as integer) as node_index,
    cast(null as double) as lon,
    cast(null as double) as lat
from {{ ref('int_trail_network__edges') }}
where false
