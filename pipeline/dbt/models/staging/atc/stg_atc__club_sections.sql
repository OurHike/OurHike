-- Which club maintains which stretch. Upstream spells the acronym column
-- ACROYNM; correcting a spelling at the rename is exactly what staging is
-- for. export_club_sections.py owns the published artifact.
with source as (
    -- dlt lands geometry as GeoJSON text (extract/_kinds.py's JSON
    -- hint); cast here, as decision 40 has staging do.
    select
        * exclude (geometry),
        st_geomfromgeojson(cast(geometry as varchar)) as geom
    from {{ source('atc', 'raw_atc__trail_club_sections') }}
),

renamed as (
    select
        {{ dbt_utils.generate_surrogate_key([
            "'trail_club_sections'",
            'globalid',
        ]) }} as club_section_key,
        cast(globalid as varchar) as source_id,
        trail_club,
        acroynm as club_acronym,
        region,
        _loaded_at as loaded_at
    from source
)

{{ dbt_utils.deduplicate(
    relation='renamed', partition_by='club_section_key', order_by='source_id'
) }}
