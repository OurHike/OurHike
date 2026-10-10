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
--
-- THE DOCUMENT IS JOINED AS TEXT. Each edge's object is written once and the
-- edges are joined with string_agg(); the two halves are then joined into
-- the outer object as text. Monthly run 28 (refresh-reference.yml
-- 37707271195, 2026-10-08) built this file as json_object() over to_json()
-- of both lists, which parses every edge back into a JSON tree, and it ran
-- out of DuckDB's 12.4 GiB alone at one thread, 5.7 s in, on the build and
-- all three retries, over 3,556,705 network pieces. Measured on DuckDB 1.5.4
-- the same day, 3,500,000 synthetic edges at a 12.4 GiB limit: that form ran
-- out the same way; to_json() of the list joined as text peaked at 9.27 GiB
-- in 34.0 s; this form at 5.84 GiB in 24.4 s. All three wrote the same bytes
-- on 20,000 edges with double lengths, null blazes, and names with quotes, a
-- slash, a backslash, a tab, a control character and non-ASCII letters.
with nodes as (
    select coalesce(list([lon, lat] order by node_index), []) as nodes
    from {{ ref('int_trail_network__nodes') }}
),

edges as (
    select
        coalesce(
            '['
            || string_agg(
                cast(
                    json_object(
                        'from', from_node,
                        'to', to_node,
                        'length_m', length_m,
                        'trail_id', trail_id,
                        'source', source_key,
                        'name', name,
                        'blaze_color', blaze_color
                    ) as varchar
                ),
                ','
                order by edge_index
            )
            || ']',
            '[]'
        ) as edges
    from {{ ref('trail_network') }}
)

select
    '{"nodes":'
    || cast(to_json(nodes.nodes) as varchar)
    || ',"edges":'
    || edges.edges
    || '}' as graph_json
from nodes
cross join edges
