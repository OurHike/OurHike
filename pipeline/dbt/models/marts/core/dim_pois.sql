-- The unified POI mart - ROADMAP.md's "Unified POI schema" item, delivered
-- for the Phase A slice (#99, #100). Adds exactly one thing over the
-- union: a stable surrogate key. Warehouse-internal for now; wiring into
-- export_poi.py's artifacts is deliberately later work (DBT.md's scope
-- boundaries).
select
    {{ dbt_utils.generate_surrogate_key(['source', 'source_id']) }} as poi_key,
    source,
    source_id,
    name,
    poi_type,
    confidence,
    longitude,
    latitude,
    loaded_at
from {{ ref('int_pois_unioned') }}
