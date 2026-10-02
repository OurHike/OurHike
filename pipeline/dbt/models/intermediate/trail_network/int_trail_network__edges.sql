-- INTERFACE: zero rows until tl-net's noding fills this model. The columns
-- are the contract the elevation family's network models read
-- (export_network_elevation.py and export_network_profile.py today), so they
-- are fixed now and the rows arrive later. It reads the network's published
-- lines, the graph's input, only so that it is not a root model.
--
-- One row per junction-graph edge, as build_trail_graph.py publishes it:
-- edge_index is the edge's place in trail_graph.json's `edges` and in
-- trail_graph_geometry.json, the alignment every companion file keeps
-- ("entry `i` here describes edge `i`"). from_node and to_node are the
-- published `from` and `to`, length_m the published `length_m` (2 decimals),
-- and geom_geojson a GeoJSON LineString whose `coordinates` are exactly the
-- edge's entry in trail_graph_geometry.json (6 decimals, lon/lat, from->to).
select
    cast(null as varchar) as edge_id,
    cast(null as integer) as edge_index,
    cast(null as varchar) as club,
    cast(null as varchar) as source_key,
    cast(null as timestamptz) as _loaded_at,
    cast(null as varchar) as trail_id,
    cast(null as varchar) as name,
    cast(null as varchar) as blaze_color,
    cast(null as integer) as from_node,
    cast(null as integer) as to_node,
    cast(null as double) as length_m,
    cast(null as varchar) as geom_geojson
from {{ ref('int_trail_lines__network_published') }}
where false
