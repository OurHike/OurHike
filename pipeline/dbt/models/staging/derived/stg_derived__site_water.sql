-- Which A.T. shelters and campsites have water a hiker can walk to:
-- step_site_water's table (pipeline/step_site_water.py), staged like any
-- table a source lands, one row per site. The water's fields come out of the
-- record's JSON under the names the file gives them; nothing is judged here,
-- because every gate ran in the step (fetch_trail_water.py's build()).
with source as (
    select * from {{ source('derived', 'site_water') }}
),

renamed as (
    select
        {{ dbt_utils.generate_surrogate_key([
            "'site_water'",
            'layer',
            'atc_global_id',
        ]) }} as site_water_key,
        site_row,
        layer,
        atc_global_id,
        atc_name,
        water is not null as has_water,
        water,
        cast(json_extract(water, '$.lon') as double) as water_lon,
        cast(json_extract(water, '$.lat') as double) as water_lat,
        json_extract_string(water, '$.stream_id') as stream_id,
        json_extract_string(water, '$.name') as water_name,
        json_extract(water, '$.sources') as sources,
        json_extract_string(water, '$.flow') as flow,
        json_extract_string(water, '$.flow_source') as flow_source,
        unresolved,
        candidate,
        _loaded_at
    from source
)

{{ dbt_utils.deduplicate(
    relation='renamed', partition_by='site_water_key', order_by='site_row'
) }}
