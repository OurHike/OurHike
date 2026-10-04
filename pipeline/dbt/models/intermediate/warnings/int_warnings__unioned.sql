-- The warnings that are not notices a club files under closures (pipeline/
-- ELT.md's warnings mart, decision 2): NWS's relayed alerts, OurHike's
-- serious reports, and every club's notice its club files under warnings
-- (int_closures__club_notices, decision 53's phase C), one row each, by
-- name, nothing filtered. The warnings mart adds the notices
-- int_closures__unioned holds that do not block the trail.
-- No hazard POI branch: ELT.md's ledger, "No hazard POI exists to port".
with nws as (
    select * from {{ ref('int_warnings__nws_relayed') }}
),

reports as (
    select * from {{ ref('int_warnings__serious_reports') }}
),

club_notices as (
    select * from {{ ref('int_closures__club_notices') }}
    where notice_type = 'warnings'
)

select * from nws

union all by name

select * from reports

union all by name

-- A club's warnings.py notice never closes a trail (its club filed it as a
-- warning), so `obstructs_trail` is null on every one, and the warnings mart
-- reads it as not reviewed. `notice_held_because` is set where it may not
-- publish as current; int_warnings__final leaves such a row out.
select
    notice_id,
    source_row_key,
    notice_kind,
    club,
    source_key,
    obstructs_trail,
    review_state,
    title,
    category,
    locality,
    source_edited_at,
    updated_at,
    source_url,
    geom_geojson,
    held_because as notice_held_because,
    _loaded_at
from club_notices
