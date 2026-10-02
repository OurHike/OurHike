-- Where a POI cannot be: a row of int_points_of_interest__classified whose
-- point lies outside the box its source publishes in.
--
-- THE HOLE THIS CLOSES WAS PROVEN, NOT SUSPECTED. During Phase D's review a
-- verifier swapped the `st_x`/`st_y` lines in one staging model and rebuilt:
-- `PASS=145 WARN=0 ERROR=0`, a completely green run, with every DEC lean-to
-- relocated to Antarctica. `dbt_utils.accepted_range` did not catch it,
-- because a transposed pair is still inside +/-180 and +/-90, and the
-- reconciliation tests could not, because they compare ROW COUNTS. The union
-- is by name now (int_points_of_interest__unioned), which closes the route
-- that swap took, but a swap inside one staging model still unions cleanly,
-- so this stays (pipeline/ELT.md, "Geometry rules every mart obeys").
--
-- A POI in the wrong place is CLAUDE.md's first way this app can hurt
-- somebody - lost - so the asymmetry is the usual one: this test is allowed to
-- miss a subtle error, and is not allowed to pass a gross one.
--
-- THE BOXES, and what they rest on. Every POI source but one publishes in the
-- eastern United States: the A.T. runs from Springer Mountain, Georgia to
-- Katahdin, Maine, and NYS DEC, NYS OPRHP and NYC Parks all publish inside
-- New York. That box is the eastern extent with several degrees of margin on
-- every side, roughly 500 km, so an ordinary registration cannot trip it and
-- a transposition cannot survive it. USFS's recreation sites are nationwide,
-- so they keep a national bound, as pipeline/ELT.md's "Contracts" gives every
-- `national` row of trail_orgs.json: the fifty states' latitudes and
-- longitudes, with no margin a transposition could land in (a swapped
-- western site reads latitude -120).
--
-- @unvalidated Every margin is picked rather than measured: no source records
-- its own bounding box, so nothing here was computed from real geometry. What
-- would settle it is one pass over a live fetch reporting each layer's actual
-- extent, and the per-club boxes from trail_orgs.json's `states` that
-- pipeline/ELT.md's "Contracts" plans. The first eastern source outside the
-- eastern box should fail here, and that is the design rather than a
-- limitation: widening a safety bound is part of registering such a source.
--
-- Fails by returning rows, like every singular test here.
{{ config(severity='error') }}

select
    source_key,
    source_feature_id,
    name,
    lon,
    lat
from {{ ref('int_points_of_interest__classified') }}
where
    lat is not null
    and lon is not null
    and case
        when source_key = 'usfs_rec_sites'
            then
                lat not between 18.0 and 72.0
                or lon not between -180.0 and -64.0
        else lat not between 30.0 and 50.0 or lon not between -90.0 and -66.0
    end
