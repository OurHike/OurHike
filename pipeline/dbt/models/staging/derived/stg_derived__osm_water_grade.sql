-- The verdict on each corridor OSM water point: step_osm_water_grade's table
-- (pipeline/step_osm_water_grade.py), staged like any table a source lands,
-- one row per point. Nothing is judged here: the grade ran in the step,
-- through build_osm_water_reach.apply_grade_gate().
with source as (
    select * from {{ source('derived', 'osm_water_grade') }}
),

renamed as (
    select
        {{ dbt_utils.generate_surrogate_key([
            "'osm_water_grade'",
            'osm_id',
        ]) }} as osm_water_grade_key,
        osm_id,
        passes_grade,
        drop_ft,
        grade,
        grade_floored,
        reachable,
        reason,
        _loaded_at
    from source
)

{{ dbt_utils.deduplicate(
    relation='renamed', partition_by='osm_water_grade_key', order_by='osm_id'
) }}
