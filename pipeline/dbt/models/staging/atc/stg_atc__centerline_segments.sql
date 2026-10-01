-- Attributes only, geometry deliberately untouched (DBT.md's scope: the
-- spatial merging/ordering lives in export_elevation.py and the axis
-- calibration, not in SQL views). What this stages is the per-segment
-- inventory the exports do not read: surface, status, the club acronym.
with source as (
    select * from {{ source('atc', 'raw_atc__centerline') }}
),

renamed as (
    select
        {{ dbt_utils.generate_surrogate_key([
            "'centerline'",
            'globalid',
        ]) }} as trail_segment_key,
        cast(globalid as varchar) as source_id,
        name,
        status,
        surface,
        reg_acro as region_acronym,
        acronym as club_acronym,
        length_ft,
        _loaded_at as loaded_at
    from source
)

{{ dbt_utils.deduplicate(
    relation='renamed', partition_by='trail_segment_key', order_by='source_id'
) }}
