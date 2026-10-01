-- The unified POI mart - ROADMAP.md's "Unified POI schema" item. It used to
-- add one thing over the union, a surrogate of (source, source_id). Since
-- decision 40 of #1793 every staging model keys its own rows, over the
-- columns measured unique for that layer (pipeline/ELT.md, "One key per
-- table"), and this model carries that key through. The old key hashed
-- DEC's OBJECTID, which a truncate-and-reload re-mints.
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
    poi_key,
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
