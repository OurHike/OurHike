-- The unified POI mart - ROADMAP.md's "Unified POI schema" item. Adds
-- exactly one thing over the union: a stable surrogate key.
--
-- MULTI-ORGANIZATION SINCE PHASE D (#100): ATC, opentrail and NYS DEC, which
-- is the first time this table has held a POI that is not on the A.T.
--
-- STILL WAREHOUSE-INTERNAL, and Phase D makes that boundary matter more than
-- it did. Wiring this into export_poi.py's artifacts remains deliberately
-- later work (DBT.md's scope boundaries), and until it happens A ROW HERE IS
-- NOT A PUBLISHABLE POI: `public_use` carries each organization's own
-- public/internal flag unapplied, so DEC's non-public rows are present in
-- this table and absent from everything a hiker sees. Anything that ever
-- publishes from here reads public_use first.
select
    {{ dbt_utils.generate_surrogate_key(['source', 'source_id']) }} as poi_key,
    source,
    source_id,
    name,
    poi_type,
    confidence,
    public_use,
    longitude,
    latitude,
    loaded_at
from {{ ref('int_pois_unioned') }}
