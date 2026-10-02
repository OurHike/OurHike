-- INTERFACE: replace with el's model
{{ config(materialized='table') }}
--
-- Each graph edge's climb, which step_form_route prices a walk from:
-- trail_graph_elevation.json, which export_network_elevation.py writes today,
-- one row per edge in edge_index order, `[gain_ft, loss_ft]` in whole feet,
-- both null where the edge was never measured. lib/trail_graph_route.py's
-- route_climb() refuses a walk's climb whole when any edge on it is
-- unmeasured, and load_graph() prices nothing from a sidecar whose length
-- is not the graph's: absent means unknown, never zero (SH08).
--
-- Zero rows until the elevation family's network half publishes it (EL10-16,
-- stage 3 of #1793 — Rebuild the data platform as dlt → dbt: seven
-- contracted marts, a monthly refresh, published docs, and lighter phone
-- downloads). With none, step_form_route writes no sidecar, and the graph
-- prices no climb, as load_graph() does with no trail_graph_elevation.json
-- beside the graph. It reads the edges only so that it is not a root model.
select
    cast(null as integer) as edge_index,
    cast(null as integer) as gain_ft,
    cast(null as integer) as loss_ft
from {{ ref('int_trail_network__edges') }}
where false
