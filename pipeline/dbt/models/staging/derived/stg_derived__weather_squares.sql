-- The NBM weather squares build_weather_squares.py chose for a release:
-- step_weather_squares's table (pipeline/step_weather_squares.py), staged
-- like any table a source lands, the document cast to JSON and nothing else.
-- int_warnings__weather_squares and int_warnings__nws_placed read its parts,
-- the trail squares and each NWS zone's squares, as
-- export_weather_alerts.py's bake() reads the file.
--
-- Key: the release, one document per release by construction.
with source as (
    select * from {{ source('derived', 'weather_squares') }}
),

renamed as (
    select
        {{ dbt_utils.generate_surrogate_key([
            "'weather_squares'",
            'release',
        ]) }} as weather_squares_key,
        release,
        cast(document_json as json) as squares_document,
        _loaded_at as loaded_at
    from source
)

{{ dbt_utils.deduplicate(
    relation='renamed', partition_by='weather_squares_key', order_by='release'
) }}
