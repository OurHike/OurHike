{{ config(format='json_document', location='trail_graph_geometry.json') }}
-- trail_graph_geometry.json, the geometry half of the junction graph, in the
-- shape build_trail_graph.py's write_artifact() writes (decision 44's v1): a
-- bare array, one entry per edge in edge_index order, each the edge's
-- vertices as [lon, lat] pairs at 6 decimals, from its `from` node to its
-- `to`. INDEX-ALIGNED with trail_graph.json's `edges`, because both are read
-- from the trail_network mart in one order: edge 40's highlight drawn from
-- edge 41's vertices would be a route on the wrong trail, and the client
-- refuses a file whose length disagrees with the edges it holds.
--
-- A bare array is a document COPY's JSON format cannot write, so this is
-- phone_file's json_document: the whole file as one text column, written
-- verbatim.
select
    coalesce(
        cast(
            to_json(
                list(
                    json_extract(geom_geojson, '$.coordinates')
                    order by edge_index
                )
            ) as varchar
        ),
        '[]'
    ) as geometry_json
from {{ ref('trail_network') }}
