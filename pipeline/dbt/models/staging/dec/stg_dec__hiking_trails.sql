-- DEC's statewide hiking-trail network, attributes only - geometry stays in
-- the Python spatial scripts, per DBT.md's scope line, exactly as
-- stg_atc__centerline_segments does for the A.T.
--
-- 5,286 polyline segments, fetched whole and counted 2026-08-25 against the
-- 5,277 the survey read on 2026-08-11, so this layer moves. Every column
-- below is in sources.json's measured field list for that same date.
--
-- FOUR THINGS THE COLUMNS DO NOT SAY ON THEIR OWN.
--
-- (1) `marker` is this pipeline's blaze (DEC aliases it 'Trail Marker
--     Color') and is a coded domain whose codes ARE the words. No
--     accepted_values test on it, deliberately and for the same reason
--     stg_atc__side_trails has none: the live values on the 5,286 rows
--     include 2,929 blank or null and one 'ORANGE AND RED' that DEC's own
--     domain does not declare. The domain is the finding, not a constraint.
--
-- (2) `foot` reads Y on 4,050 rows and M on 1,236 and nothing else. Reading
--     M as "DEC maintains this corridor for foot travel" is OURS rather than
--     DEC's - sources.json's foot_allowed_comment holds the reasoning and
--     the live domain read (Y=YES, N=NO, U=UNDECIDED, M=MAINTAINED,
--     -99=NO JURISDICTION, read off the field metadata 2026-08-25). This
--     model does not apply that reading; it passes the raw code through so
--     the one place that interprets it stays export_nearby_trails.py.
--
-- (3) THERE IS NO STATUS COLUMN. DEC publishes no closure state on this
--     layer, and `publicuse` reads 'Y' on all 5,286 rows, so it is a
--     layer-wide constant rather than a filter. No status column is
--     synthesised here - inventing one is the failure this project's closure
--     treatment exists to avoid (CLAUDE.md's four ways).
--
-- (4) BOTH ID COLUMNS ARE STAGED, on purpose. DEC spells the stable one
--     GLOBALID where lib/feature_id.py looks for GlobalID, so the published
--     ids fall back to OBJECTID - unique across the fetched 5,286 and stable
--     within a fetch, but renumbered by a DEC republish. Carrying both keeps
--     that visible instead of burying it; source_id is OBJECTID to match
--     what actually ships today.
--
-- The layer's name oversells it and the ASSET column is where that shows:
-- 'Hiking Trails' is DEC's per-use split, so a row is here because foot
-- travel is allowed on it, not because it is a footpath - 446 rows are
-- ASSET 'SNOWMOBILE TRAIL' and 456 are unpaved roads.
with source as (
    select * from {{ source('dec', 'raw_dec__dec_hiking_trails') }}
)

select
    cast(objectid as varchar) as source_id,
    globalid as stable_id,
    name,
    unit,
    facility,
    asset,
    descrip as description,
    miles,
    marker,
    foot,
    publicuse as public_use,
    updated,
    _loaded_at as loaded_at
from source
