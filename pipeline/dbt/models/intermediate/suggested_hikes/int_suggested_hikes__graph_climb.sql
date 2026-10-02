{{ config(materialized='table') }}
--
-- Each graph edge's climb, which step_form_route prices a walk from:
-- trail_graph_elevation.json, which export_network_elevation.py writes today
-- and pub_trail_graph_elevation writes from int_elevation__edge_climbs, one
-- row per edge in edge_index order, `[gain_ft, loss_ft]` in whole feet, both
-- null where the edge was never measured. lib/trail_graph_route.py's
-- route_climb() refuses a walk's climb whole when any edge on it is
-- unmeasured, and load_graph() prices nothing from a sidecar whose length
-- is not the graph's: absent means unknown, never zero (SH08).
--
-- The same entries the writer publishes, so a hike is priced from exactly the
-- file a phone would read: an edge whose source may not publish is null here
-- as it is there, and pub_trail_graph_elevation's parity against
-- export_network_elevation.py (no differences on 30,004 edges cut from ATC's
-- live centerline, el, 2026-10-02) is what holds these values to today's.
select
    edge_index,
    case when gain_ft is not null and may_publish then gain_ft end as gain_ft,
    case when gain_ft is not null and may_publish then loss_ft end as loss_ft
from {{ ref('int_elevation__edge_climbs') }}
