-- Decision 67 (the maintainer, poll, 2026-10-04): a hunting area, a
-- recreational shooting site or a burned area is an area a hiker walks into,
-- with an advisory on the stretch inside it, and the trail stays open. So no
-- row of a source seeds/notice_hazard_areas.csv lists may land in the
-- closures mart, and none in the warnings mart may say it blocks the trail.
-- Each of the five is a warnings.py source today, whose notices never close
-- a trail (int_warnings__unioned); this holds that for whatever source the
-- seed lists next, and for a source a later change moves to closures.py.
-- Returns one row per notice that breaks it.
with hazards as (
    select distinct source_key from {{ ref('notice_hazard_areas') }}
)

select
    'closures' as mart,
    closures.closure_id as notice_id,
    closures.source_key
from {{ ref('closures') }} as closures
inner join hazards on closures.source_key = hazards.source_key

union all

select
    'warnings' as mart,
    warnings.warning_id as notice_id,
    warnings.source_key
from {{ ref('warnings') }} as warnings
inner join hazards on warnings.source_key = hazards.source_key
where coalesce(warnings.obstructs_trail, false)
