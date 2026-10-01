-- ATC's own mile scale - the calibration authority for the whole mile axis
-- (#652): export_elevation and every published POI mile ride these values.
-- Point_ID is the identity; the layer has no GlobalID.
with source as (
    select * from {{ source('atc', 'raw_atc__half_mile_points_from_springer') }}
),

renamed as (
    select
        {{ dbt_utils.generate_surrogate_key([
            "'half_mile_points_from_springer'",
            'point_id',
        ]) }} as mile_marker_key,
        cast(point_id as varchar) as source_id,
        measure as measure_mi,
        measurem as measure_m,
        st_x(geom) as longitude,
        st_y(geom) as latitude,
        _loaded_at as loaded_at
    from source
)

{{ dbt_utils.deduplicate(
    relation='renamed', partition_by='mile_marker_key', order_by='source_id'
) }}
