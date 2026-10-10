-- OurHike's public reports (extract/_shared/ourhike/reports.py,
-- export_conditions.py's PUBLIC_REPORTS_SQL run whole), keyed (decision 40),
-- every severity and nothing filtered. conditions/reports.json carries every
-- one of them (pub_conditions_reports), and int_warnings__serious_reports
-- takes the serious ones for the warnings mart (WN10). `type` and
-- `timestamp` are keywords, so they are renamed here and written back under
-- their own names by the writer.
--
-- Key: the report's UUID primary key.
with source as (
    select * from {{ source('ourhike', 'raw_ourhike__reports') }}
),

renamed as (
    select
        {{ dbt_utils.generate_surrogate_key([
            "'ourhike_reports'",
            'id',
        ]) }} as ourhike_report_key,
        id as report_uuid,
        type as report_type,
        poi_id,
        lat,
        lon,
        mile,
        reporter_type,
        timestamp as reported_at,
        note,
        cast(follow_up as json) as follow_up,
        status as report_status,
        visibility,
        severity as report_severity,
        verified_at,
        _loaded_at,
        _dlt_id
    from source
)

{{ dbt_utils.deduplicate(
    relation='renamed', partition_by='ourhike_report_key', order_by='_dlt_id'
) }}
