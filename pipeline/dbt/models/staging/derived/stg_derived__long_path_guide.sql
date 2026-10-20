-- NYNJTC's Long Path guide as waypoints: step_long_path_guide's table
-- (pipeline/step_long_path_guide.py), staged like any table a source lands,
-- one row per record. Nothing is classified or placed here: that is
-- build_records()', in the step.
with source as (
    select * from {{ source('derived', 'long_path_guide') }}
),

renamed as (
    select
        {{ dbt_utils.generate_surrogate_key([
            "'long_path_guide'",
            'id',
        ]) }} as long_path_guide_key,
        record_row,
        id,
        poi_type,
        trail_id,
        source,
        source_feature_id,
        name,
        lat,
        lon,
        confidence,
        description,
        lp_section,
        section_mile,
        placement,
        source_url,
        position_error_m,
        off_trail_miles,
        water_reliability,
        record,
        _loaded_at
    from source
)

{{ dbt_utils.deduplicate(
    relation='renamed', partition_by='long_path_guide_key', order_by='record_row'
) }}
