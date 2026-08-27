-- DEC's back-country asset inventory, staged and DELIBERATELY NOT UNIONED
-- into dim_pois - the same posture stg_atc__bridges holds, reached by a
-- different road and worth stating plainly because the name invites the
-- opposite reading.
--
-- THIS IS NOT A POI LAYER. DEC's own description calls it "point data
-- locating and differentiating assets on state lands... man-made items,
-- which require periodic maintenance or inspection". 21,468 points counted
-- live 2026-08-27; the largest single value is CULVERT at 4,290 features,
-- and sources.json records that 68% of the layer is things no hiker wants a
-- pin for. The entry declares NO `poi_type` for exactly that reason, so
-- there is no per-layer type to stamp on a row and this model stamps none.
--
-- WHAT PUBLISHES FROM IT DOES SO THROUGH AN ALLOWLIST, in
-- export_nearby_poi.py: two poi types (privy and crossing) matched against a
-- value list plus PUBLICUSE, never a type-prefix match. Reproducing that
-- allowlist here would be two homes for one product decision, so `asset` is
-- staged raw and untyped.
--
-- `asset` IS FREE TEXT AND IT IS DIRTY: 234 values as stored, 223 after
-- trimming, including 'FORD ' beside 'FORD', a bare ' ' on 86 rows, and
-- DEC's own misspellings ('PRIMATIVE CAMPSITE'). Any match on it is
-- case-insensitive and stripped. No accepted_values test, for the same
-- reason as stg_dec__hiking_trails' marker: the domain is the finding.
--
-- `publicuse` splits the layer 7,645 Y / 13,823 N and is the only reason it
-- is publishable at all; it is carried, not applied - see stg_dec__lean_tos.
with source as (
    select * from {{ source('dec', 'raw_dec__dec_backcountry_features') }}
)

select
    cast(objectid as varchar) as source_id,
    name,
    facility,
    asset,
    publicuse as public_use,
    updated,
    _loaded_at as loaded_at
from source
