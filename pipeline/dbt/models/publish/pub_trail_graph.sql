{{ config(format='json_document', location='trail_graph.json') }}
-- trail_graph.json, the routing half of the junction graph, in the shape
-- build_trail_graph.py's write_artifact() writes (decision 44's v1): one
-- object, `nodes` then `edges`. A phone reads it at launch to say whether a
-- day hike is on offer (PlanKindSheet), and client/src/lib/trailGraph.ts
-- paths over it.
--
-- - `nodes`: [lon, lat] per node, in int_trail_network__nodes' order;
-- - `edges`: one object per edge in edge_index order, its keys in
--   build_graph()'s order, `from`, `to`, `length_m`, `trail_id`, `source`,
--   `name`, `blaze_color`, every one present and null where unknown, as the
--   Python writes None.
-- No vertices: those are trail_graph_geometry.json's, index-aligned with
-- `edges` (pub_trail_graph_geometry), because the geometry is by far the
-- heavier half and is only needed once the builder opens.
--
-- phone_file's json_document format, the whole object as one text column:
-- the file's key is `nodes`, a list, and no scalar column is left for the
-- writer's key test to hold.
with nodes as (
    select coalesce(list([lon, lat] order by node_index), []) as nodes
    from {{ ref('int_trail_network__nodes') }}
),

edges as (
    select
        coalesce(
            list(
                json_object(
                    'from', from_node,
                    'to', to_node,
                    'length_m', length_m,
                    'trail_id', trail_id,
                    'source', source_key,
                    'name', name,
                    'blaze_color', blaze_color
                )
                order by edge_index
            ),
            cast([] as json[])
        ) as edges
    from {{ ref('trail_network') }}
)

select
    cast(
        json_object(
            'nodes', to_json(nodes.nodes), 'edges', to_json(edges.edges)
        ) as varchar
    ) as graph_json
from nodes
cross join edges
