-- Decision 7's split is a partition: every notice from a source that passed
-- int_closures__gate and may publish lands in exactly one of the closures and
-- warnings marts, by its `obstructs_trail` (true to closures; false and null
-- to warnings, never dropped), and nothing else lands in either as a notice
-- (pipeline/ELT.md, "The eleven marts").
--
-- OVER PASSING SOURCES ONLY. A source the gate holds back lands in neither
-- mart by design, so its last good file stays on the phone, and counting its
-- rows here would fail the build for the very case the gate exists to
-- contain. The test reads the union joined to the passing sources, not the
-- whole union. Returns one row per notice that lands in no mart, in both, or
-- in a mart it should not.
--
-- THE CLUB NOTICES (decision 53, phase C) are counted as they land: a
-- closures-type one through int_closures__unioned like any notice, unless
-- its own end date or status holds it back (`notice_held_because`), which
-- lands it in neither; and a warnings-type one through int_warnings__unioned,
-- which only the warnings mart takes.
with passing as (
    select gate.source_key
    from {{ ref('int_closures__gate') }} as gate
    inner join {{ ref('int_sources__publication') }} as publishable
        on gate.source_key = publishable.source_key
    where gate.passed and publishable.may_publish
),

notices as (
    select notices.notice_id
    from {{ ref('int_closures__unioned') }} as notices
    inner join passing on notices.source_key = passing.source_key
    where notices.notice_held_because is null
    union all
    select warning_notices.notice_id
    from {{ ref('int_warnings__unioned') }} as warning_notices
    inner join passing on warning_notices.source_key = passing.source_key
    where
        starts_with(warning_notices.notice_kind, 'club_')
        and warning_notices.notice_held_because is null
),

landed as (
    select
        closure_id as notice_id,
        'closures' as mart
    from {{ ref('closures') }}
    union all
    select
        warning_id as notice_id,
        'warnings' as mart
    from {{ ref('warnings') }}
    where warning_kind = 'org_notice'
),

counted as (
    select
        coalesce(notices.notice_id, landed.notice_id) as notice_id,
        notices.notice_id is not null as is_passing_notice,
        count(landed.mart) as marts_landed_in,
        string_agg(landed.mart, ', ' order by landed.mart) as landed_in
    from notices
    full outer join landed on notices.notice_id = landed.notice_id
    group by
        coalesce(notices.notice_id, landed.notice_id),
        notices.notice_id is not null
)

select *
from counted
where not is_passing_notice or marts_landed_in != 1
