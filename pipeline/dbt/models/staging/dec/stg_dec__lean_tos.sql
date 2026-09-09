-- DEC's lean-tos in the unified POI column shape - the first non-A.T. POI
-- source the warehouse has ever held (Phase D, #100). Every literal below is
-- sources.json's own, measured, rather than a call made here:
--
--   poi_type 'shelter'    the entry's declared `poi_type`
--   source_id OBJECTID    its `id_field`
--   name NAME             its `name_field`
--   public_use PUBLICUSE  its `public_field`
--
-- The whole field list was measured live 2026-08-27 (315 rows statewide), so
-- the columns here are transcription, not invention.
--
-- CONFIDENCE IS 'high', AND THAT IS export_nearby_poi.py's CALL rather than a
-- second opinion: a DEC entry declares no `public_flag_sets_confidence`, so
-- that module's public_verdict() returns CONFIDENCE_HIGH for every row it
-- keeps. OPRHP's facilities layer is the one that differs, and it is
-- deliberately not unioned - see stg_oprhp__facilities.
--
-- NO CAPACITY COLUMN, because the layer has none. sources.json's measurement
-- is explicit: "nothing states how many the shelter sleeps, so a DEC shelter
-- exports without capacity - absent meaning unknown, never zero". A staging
-- model is exactly where that absence has to survive.
--
-- PUBLICUSE IS CARRIED, NOT APPLIED, and this is the one decision in this
-- model worth arguing with. export_nearby_poi.py DROPS the N side (on the
-- big backcountry layer that side is 13,823 culverts, gates and sign posts).
-- This model keeps every row and passes the flag through, because dim_pois is
-- a warehouse-internal mart rather than a published artifact, and
-- re-implementing a safety filter in SQL beside the tested Python one is the
-- second parallel pipeline #100 exists to prevent. The cost is real and is
-- named in DBT.md: anything that ever publishes FROM dim_pois must read
-- public_use first, and a row here is not a shippable POI.
with source as (
    select * from {{ source('dec', 'raw_dec__dec_lean_tos') }}
)

select
    'dec_lean_tos' as source,
    cast(objectid as varchar) as source_id,
    name,
    'shelter' as poi_type,
    'high' as confidence,
    publicuse as public_use,
    st_x(geom) as longitude,
    st_y(geom) as latitude,
    _loaded_at as loaded_at
from source
