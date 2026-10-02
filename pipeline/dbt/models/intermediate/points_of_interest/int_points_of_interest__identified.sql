{{ config(materialized='table') }}
-- Every POI in its file's ground, with the id it publishes under (PO23).
--
-- THE A.T. FAMILY PUBLISHES UNDER THE IDENTITY LEDGER'S IDS:
-- export_poi.py's apply_ledger_ids(), the load-bearing line of
-- features/POI_IDENTITY.md. A row whose (source, source_feature_id) is a
-- LIVE ledger row takes that row's poi_id; any other keeps its derived id,
-- `{source}:{source_feature_id}`, which is exactly the id
-- reconcile_poi_identity.py mints for a new feature, so the two agree until
-- an upstream re-key makes them differ, and on that day this join is what
-- keeps a hiker's photos anchored. On reference/poi_identity.json as it
-- stands every live id equals its derived one (all 3,151 live rows, read
-- 2026-10-02), so today this changes no id.
--
-- The ledger is the committed reviewed file (base_ourhike__poi_identity),
-- never a proposal: writing it stays reconcile_poi_identity.py's, a Python
-- step (PO22), because it carries state across releases and never re-mints.
--
-- THE OTHER ORGANIZATIONS' POIs ARE UNLEDGERED: export_nearby_poi.py
-- publishes each under its derived id, and so does this (pipeline/ELT.md,
-- "Where state lives": the 20,506 nearby_poi.geojson features have no ledger
-- rows, an open question for the maintainer).
with in_corridor as (
    select * from {{ ref('int_points_of_interest__in_corridor') }}
),

live_ledger as (
    select
        poi_id,
        source,
        source_feature_id
    from {{ ref('base_ourhike__poi_identity') }}
    where retired is null
)

select
    coalesce(live_ledger.poi_id, in_corridor.derived_id) as poi_id,
    in_corridor.*
from in_corridor
left join live_ledger
    on
        in_corridor.phone_files = 'poi_by_type'
        and in_corridor.source = live_ledger.source
        and in_corridor.source_feature_id = live_ledger.source_feature_id
