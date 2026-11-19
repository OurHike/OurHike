-- The size of OurHike's own database (extract/_shared/ourhike/database_size.py,
-- pipeline/lib/database_size.py's DATABASE_SIZE_SQL), keyed, in bytes and in
-- the whole megabytes the data-quality page shows and
-- tests/singular/assert_the_database_stays_under_its_plan.sql holds to the
-- plan. Read through raw_or_empty(), so a leg that has never landed the size
-- builds as no row rather than failing the hourly build, as a missing
-- conditions table read by source() would (extract/_run.py's
-- NEW_TABLES_PER_LEG_RUN): the size is the page's, never a reason to hold a
-- closure back.
--
-- Key: the load that read it, since the table holds one row per read.
with source as (
    select * from {{ raw_or_empty(
        source('ourhike', 'raw_ourhike__database_size'),
        ['database_bytes:bigint', '_dlt_load_id']
    ) }}
),

renamed as (
    select
        {{ dbt_utils.generate_surrogate_key([
            "'ourhike_database_size'",
            '_dlt_load_id',
        ]) }} as ourhike_database_size_key,
        database_bytes,
        -- Megabytes of 1,048,576 bytes (lib/database_size.py's MEGABYTE),
        -- rounded down, so that 400 here is the backend's own 80% of
        -- `database_quota_mb` to the byte (app/core/analytics_quality.py's
        -- STORAGE_WARN_SHARE, which compares bytes).
        cast(floor(database_bytes / 1048576) as bigint) as database_mb,
        _loaded_at,
        _dlt_id
    from source
)

{{ dbt_utils.deduplicate(
    relation='renamed', partition_by='ourhike_database_size_key', order_by='_dlt_id'
) }}
