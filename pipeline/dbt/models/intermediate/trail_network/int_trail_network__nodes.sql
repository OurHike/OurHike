{{ config(materialized='table') }}
{%- set decimals = 6 %}
-- trail_graph.json's `nodes`: one row per published node, in the order
-- build_graph() numbers them, as [lon, lat] (TN06). A node's point is where
-- the node grid first made it, the first end to reach that place
-- (int_trail_network__node_lookups); a merged node's is its group's lowest.
-- Taken back to lon/lat with ST_Transform (pyproj's doubles, measured on
-- 200,000 of 200,000 points) and rounded to 6 decimals as Python's round()
-- rounds (printf). A node reached only by an edge compaction dropped is
-- still here, as the Python numbers it before the drop.
with numbered as (
    select
        from_root as root_raw,
        from_node as node_index
    from {{ ref('int_trail_network__raw_edges') }}
    union distinct
    select
        to_root as root_raw,
        to_node as node_index
    from {{ ref('int_trail_network__raw_edges') }}
),

makers as (
    select
        node_raw,
        st_transform(
            st_point(x, y), 'EPSG:5070', 'EPSG:4326', always_xy := true
        ) as lon_lat
    from {{ ref('int_trail_network__node_lookups') }}
    where makes_node
)

select
    cast(numbered.node_index as integer) as node_index,
    cast(
        printf('%.{{ decimals }}f', st_x(makers.lon_lat)) as double
    ) as lon,
    cast(
        printf('%.{{ decimals }}f', st_y(makers.lon_lat)) as double
    ) as lat
from numbered
inner join makers on numbered.root_raw = makers.node_raw
