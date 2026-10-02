{{ config(format='json', location='conditions_reports.json') }}
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
-- NOTHING IS WRITTEN, and the phone keeps its last good file, when
-- int_sources__publication holds OurHike's reports back, or when a row
-- carries a coordinate or a mile that is not a finite number, as
-- pub_conditions_closures says.
--
-- `generated_at` is dbt's run_started_at: one clock for this file and
-- conditions/closures.json, as export_conditions.py's main() keeps one.
with reports as (
    select * from {{ ref('base_ourhike__reports') }}
    where
        report_status in ('verified', 'resolved')
        and visibility = 'public'
),

publication as (
    select * from {{ ref('int_sources__publication') }}
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
        ) as reports,
        count(*) filter (
            where not (
                coalesce(isfinite(lat), true)
                and coalesce(isfinite(lon), true)
                and coalesce(isfinite(mile), true)
            )
        ) as rows_not_finite
    from reports
),

judged as (
    select
        published.reports,
        published.rows_not_finite,
        coalesce(publication.may_publish, false) as may_publish,
        coalesce(publication.publication_rule, 'no row') as publication_rule
    from published
    left join publication on true
)

select
    case
        when may_publish and rows_not_finite = 0
            then {{ python_run_stamp() }}
        when not may_publish
            then error(
                'conditions/reports.json is not written: '
                || 'int_sources__publication holds ourhike_reports back ('
                || publication_rule || ')'
            )
        else error(
            'conditions/reports.json is not written: ' || rows_not_finite
            || ' row(s) carry a coordinate or a mile that is not a finite '
            || 'number, and JSON.parse on a phone rejects the whole document'
        )
    end as generated_at,
    reports
from judged
