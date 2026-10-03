-- The extract's run log (extract/_run.py's write_run_log()), one row per
-- resource per run, keyed (decision 40), with nothing filtered.
-- int_closures__gate reads the count an upstream gave in the run that loaded
-- its rows.
--
-- Key: the run and the resource, which write_run_log() logs once each.
with source as (
    select * from {{ source('extract', '_extract_runs') }}
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
        resource_name,
        table_name,
        verdict,
        outcome,
        -- Cast because a column null on every row of a log lands untyped.
        cast(rows as bigint) as rows_loaded,
        cast(count_proof as bigint) as count_proof,
        load_id,
        checked_at,
        _dlt_id
    from source
)

{{ dbt_utils.deduplicate(
    relation='renamed', partition_by='extract_run_key', order_by='_dlt_id'
) }}
