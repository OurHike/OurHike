-- NYS Parks' facility points - 8,823 statewide, measured 2026-08-18 - staged
-- and DELIBERATELY NOT UNIONED into dim_pois, the same posture
-- stg_atc__bridges and stg_dec__backcountry_features hold.
--
-- WHY NOT UNIONED, stated carefully because this layer DOES publish POIs
-- and a reader could reasonably expect it here. sources.json declares no
-- layer-wide `poi_type` for it, because it does not have one: 158 distinct
-- `Sub_Asset` values, measured live 2026-08-27, of which
-- export_nearby_poi.py types thirteen through OPRHP_SUB_ASSET_TYPES and
-- ships the rest as nothing. That per-row map carries its own allowlist AND
-- its own named exclusions, and reproducing it in SQL would be two homes for
-- one product decision - the same reason stg_dec__backcountry_features is
-- not unioned either.
--
-- THE EXCLUSIONS ARE THE PART THAT MATTERS. 136 'Water Spigot' and 15
-- 'Drinking Fountain' rows sit in that column, and export_nearby_poi.py's
-- NAMED_EXCLUSIONS holds BOTH back as a water holdback - no seasonal shutoff
-- is recorded anywhere, so the pipeline declines to call them water rather
-- than shipping water it cannot vouch for. 'Mineral Spring', 'Water Tower'
-- and 'Waterfall' are also in the column and are not drinking water at all.
-- A staging model that stamped a poi_type would be making the water call in
-- the quietest possible place. It stays unmade here, and the raw value is
-- staged so whatever makes it can see what it is deciding about.
--
-- `asset` IS A CODED INTEGER 1-17 WHOSE DOMAIN THE SERVICE DOES NOT PUBLISH,
-- so a facility's type is only readable through `sub_asset`'s free text.
-- That is the join hazard to solve before any of these become waypoints, and
-- staging the integer undecoded is how it stays visible rather than being
-- half-solved by a guess.
--
-- TWO PUBLIC FLAGS, AND THE OBVIOUS ONE IS THE WRONG ONE. `Public_` reads Y
-- on all 8,823 rows and therefore discriminates nothing (measured
-- 2026-08-27). `ParksApp` is the field that does, 5,822 Y / 3,000 N - but it
-- records what OPRHP's own visitor app SHOWS rather than what exists on the
-- ground, so export_nearby_poi.py reads its N side as LOW CONFIDENCE instead
-- of dropping it: filtering on it would discard every one of OPRHP's 37
-- lean-tos, none of which are in that app. Both columns are staged, neither
-- is applied, and the naming here says which is which.
--
-- `name` is populated on 1,631 of 8,823 rows (18%) and the layer's own alias
-- flags it '(Legacy Field)'. `facility` is populated on all 8,823 and is the
-- PARK's name, not the feature's - staged under a name that says so, because
-- publishing 'Beaver Island State Park' as the name of a bridge inside it is
-- the display-outruns-its-source failure in miniature.
with source as (
    select * from {{ source('oprhp', 'raw_oprhp__oprhp_facilities') }}
)

select
    name as feature_name,
    facility as park_name,
    asset as asset_code,
    sub_asset,
    parksapp as in_parks_app,
    public_ as public_flag,
    st_x(geom) as longitude,
    st_y(geom) as latitude,
    _loaded_at as loaded_at
from source
