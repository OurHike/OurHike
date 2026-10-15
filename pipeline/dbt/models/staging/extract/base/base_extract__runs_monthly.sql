-- The extract's run log as the monthly lane's nodes read it: the lane copy
-- of base_extract__runs, over the source table _extract_runs_monthly (its
-- description in _extract__sources.yml says why there are two). One row per
-- resource per run, keyed (decision 40), with nothing filtered.
-- int_sources__data_edited dates each layer from it.
--
-- Key: the run and the resource, which write_run_log() logs once each, the
-- same key base_extract__runs builds, since both read the same rows.
with source as (
    select * from {{ source('extract', '_extract_runs_monthly') }}
),

renamed as (
    select
        {{ dbt_utils.generate_surrogate_key([
            "'extract_runs'",
            'run_id',
            'resource_name',
        ]) }} as extract_run_key,
        run_id,
        pipeline as lane,
        club,
        resource_name,
        table_name,
        outcome,
        -- Cast because a column null on every row of a log lands untyped.
        cast(data_last_edit_date as bigint) as data_last_edit_date,
        checked_at,
        _dlt_id
    from source
)

{{ dbt_utils.deduplicate(
    relation='renamed', partition_by='extract_run_key', order_by='_dlt_id'
) }}
