-- OurHike's serious reports, for the warnings mart (WN10): the public
-- verified or resolved reports a moderator escalated to `serious`
-- (HIKER_SAFETY.md's severity tier; app/models/report.py's Severity). A
-- resolved one stays, because a blowdown someone has since cleared reads as
-- "Fixed" and is information (export_conditions.py's docstring).
--
-- conditions/reports.json is NOT written from here: it carries every public
-- report, serious or not, as PUBLIC_REPORTS_SQL selects them, and
-- pub_conditions_reports reads base_ourhike__reports for it.
--
-- The query's own predicate is applied again, so a report the extract
-- should never have landed is left out rather than published as
-- moderator-verified: a display may not outrun its source.
with reports as (
    select * from {{ ref('base_ourhike__reports') }}
)

select
    'ourhike_reports:' || report_uuid as notice_id,
    ourhike_report_key as source_row_key,
    'ourhike_report' as notice_kind,
    'ourhike' as club,
    'ourhike_reports' as source_key,
    false as obstructs_trail,
    'moderator_verified' as review_state,
    report_uuid,
    report_type,
    poi_id,
    lat,
    lon,
    mile as report_mile,
    reporter_type,
    reported_at,
    note,
    follow_up,
    report_status,
    visibility,
    report_severity,
    verified_at,
    _loaded_at
from reports
where
    report_severity = 'serious'
    and report_status in ('verified', 'resolved')
    and visibility = 'public'
