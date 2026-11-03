-- trail_graph_elevation.json and trail_graph_profile.json describe
-- trail_graph.json's edges by position: entry i is edge i, and nothing in an
-- entry names its edge (export_network_elevation.py; publish.py's #1313
-- comment). pub_trail_graph_elevation and pub_trail_graph_profile write one
-- entry per row of int_trail_network__edges in edge_index order, so the
-- entries line up with trail_graph.json only if edge_index runs 0, 1, 2 ...
-- with no gap and no repeat: a gap would shift every later edge's climb onto
-- its neighbour's name, which is a confidently wrong climb on the one
-- figure a hiker prices a walk with. Returns a row when the numbering is not
-- exactly 0 to n - 1.
select
    count(*) as edges,
    count(distinct edge_index) as distinct_indexes,
    min(edge_index) as first_index,
    max(edge_index) as last_index
from {{ ref('int_trail_network__edges') }}
having
    count(*) > 0
    and (
        count(distinct edge_index) != count(*)
        or min(edge_index) != 0
        or max(edge_index) != count(*) - 1
    )
