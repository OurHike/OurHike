{{ config(
    format='json',
    location='conditions_reports.json',
    meta={'when_empty': 'keep_last_file', 'gate': 'ourhike_reports'},
) }}
-- conditions/reports.json, OurHike's public reports, in the shape
-- export_conditions.py's build_document("reports", ...) writes:
-- `generated_at` and every row PUBLIC_REPORTS_SQL selects, in its order
-- ("timestamp", id), its timestamps stamped by _stamp_utc().
--
-- EVERY PUBLIC REPORT, NOT ONLY THE SERIOUS ONES. The file carries every
-- verified or resolved public report, whatever its severity, and the phone
-- reads `severity` itself; the warnings mart takes only the serious ones
-- (int_warnings__serious_reports, WN10). So this reads
-- base_ourhike__reports, the query's own rows, with the query's predicate
-- applied again: a report the extract should never have landed is left out
-- rather than published.
--
-- NO ROW, SO NO FILE, while int_closures__gate holds OurHike's reports back
-- (`meta.gate`): because int_sources__publication does, or for a number that
-- is not finite. The phone keeps its last file, and publish.py fails the run
-- after publishing the rest.
--
-- `generated_at` is dbt's run_started_at: one clock for this file and
-- conditions/closures.json, as export_conditions.py's main() keeps one.
with reports as (
    select * from {{ ref('base_ourhike__reports') }}
    where
        report_status in ('verified', 'resolved')
        and visibility = 'public'
),

gate as (
    select * from {{ ref('int_closures__gate') }}
    where source_key = 'ourhike_reports'
),

published as (
    select
        coalesce(
            list(
                json_object(
                    'id', report_uuid,
                    'type', report_type,
                    'poi_id', poi_id,
                    'lat', lat,
                    'lon', lon,
                    'mile', mile,
                    'reporter_type', reporter_type,
                    'timestamp', {{ python_utc_isoformat('reported_at') }},
                    'note', note,
                    'follow_up', follow_up,
                    'status', report_status,
                    'visibility', visibility,
                    'severity', report_severity,
                    'verified_at', {{ python_utc_isoformat('verified_at') }}
                ) order by reported_at, report_uuid
            ),
            []
        ) as reports
    from reports
)

select
    {{ python_run_stamp() }} as generated_at,
    published.reports
from published
inner join gate on gate.source_key = 'ourhike_reports'
where gate.passed
