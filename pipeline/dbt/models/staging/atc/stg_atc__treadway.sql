-- The 30 built treadway segments with their construction inventory.
with source as (
    select * from {{ source('atc', 'raw_atc__at_treadway') }}
),

renamed as (
    select
        {{ dbt_utils.generate_surrogate_key([
            "'at_treadway'",
            'globalid',
        ]) }} as trail_segment_key,
        cast(globalid as varchar) as source_id,
        name,
        status,
        length_ft,
        year_built,
        comments,
        _loaded_at as loaded_at
    from source
)

{{ dedupe('renamed', 'trail_segment_key', 'source_id') }}
