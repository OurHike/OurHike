-- OSM's water points in fetch_osm_water.py's shape: step_osm_water's table
-- (pipeline/step_osm_water.py), staged like any table a source lands, one
-- row per node. Fixture mode alone lands rows until #1652 — Download OSM's
-- Geofabrik extracts at most once a month, into a private raw bucket that
-- outlives the 7-day Actions cache. The properties stay the file's JSON, so
-- a tag OSM does not carry stays absent rather than becoming a null member.
with source as (
    select * from {{ source('derived', 'osm_water') }}
),

renamed as (
    select
        {{ dbt_utils.generate_surrogate_key([
            "'osm_water'",
            'osm_id',
        ]) }} as osm_water_key,
        feature_row,
        osm_id,
        kind,
        lon,
        lat,
        properties,
        _loaded_at
    from source
)

{{ dbt_utils.deduplicate(
    relation='renamed', partition_by='osm_water_key', order_by='feature_row'
) }}
