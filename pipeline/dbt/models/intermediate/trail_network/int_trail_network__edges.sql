{{ config(materialized='table') }}
{%- set decimals = 6 %}
-- One row per junction-graph edge, as build_trail_graph.py publishes it
-- (TN07 of pipeline/ELT.md's ledger): a piece of a maintained trail line
-- between two junctions, carrying its parent line's id (published as
-- `trail_id`), source, name and blaze, because the client reads all four off
-- the edge (frame `1j` tallies legs per organization while the hiker builds;
-- frame `1l`'s turn list is spoken in trail names and blazes).
--
-- The elevation family's network models read it too, as
-- export_network_elevation.py and export_network_profile.py read
-- trail_graph.json and trail_graph_geometry.json today, so its columns are
-- the contract their port was written against:
-- - edge_index is the edge's place in trail_graph.json's `edges` and in
--   trail_graph_geometry.json, the alignment every companion file keeps
--   ("entry `i` here describes edge `i`"): the kept pieces in order, less
--   the ones compaction drops (int_trail_network__raw_edges);
-- - from_node and to_node are the published `from` and `to`, indexes into
--   int_trail_network__nodes;
-- - length_m is the piece's EPSG:5070 length at 2 decimals, measured on the
--   1 m navigation line the graph is noded from, as build_trail_graph.py
--   measures it today (decision 8's full-resolution length is not built:
--   ELT.md's TN07 row says why);
-- - geom_geojson is a GeoJSON LineString whose `coordinates` are exactly
--   the edge's entry in trail_graph_geometry.json: the piece's vertices back
--   in lon/lat, ST_Transform giving pyproj's doubles (measured 2026-10-02 on
--   200,000 of 200,000 points, int_trail_network__cuts), each rounded to 6
--   decimals as _geographic_vertices() rounds them (printf, Python's
--   round()). An edge always has two or more vertices, so `coordinates` is
--   always an array.
with raw_edges as (
    select * from {{ ref('int_trail_network__raw_edges') }}
    where not dropped_as_a_loop
),

parts as (
    select * from {{ ref('int_trail_network__routable') }}
    where refused_because is null
),

edges as (
    select
        *,
        row_number() over (order by edge_rank) - 1 as edge_index,
        list_transform(
            cast(
                json_extract(
                    st_asgeojson(
                        st_transform(
                            st_geomfromtext(geom_m_wkt),
                            'EPSG:5070',
                            'EPSG:4326',
                            always_xy := true
                        )
                    ),
                    '$.coordinates'
                ) as double[][]
            ),
            lambda point: list_transform(
                point,
                lambda coordinate: cast(
                    printf('%.{{ decimals }}f', coordinate) as double
                )
            )
        ) as coordinates
    from raw_edges
)

select
    edges.part_id || '.' || edges.piece_index as edge_id,
    cast(edges.edge_index as integer) as edge_index,
    parts.club,
    parts.source_key,
    parts._loaded_at,
    parts.trail_id,
    parts.name,
    parts.blaze_color,
    cast(edges.from_node as integer) as from_node,
    cast(edges.to_node as integer) as to_node,
    edges.length_m,
    cast(
        json_object(
            'type', 'LineString', 'coordinates', to_json(edges.coordinates)
        ) as varchar
    ) as geom_geojson
from edges
inner join parts on edges.part_id = parts.part_id
