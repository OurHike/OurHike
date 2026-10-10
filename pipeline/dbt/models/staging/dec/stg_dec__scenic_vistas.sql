-- DEC's scenic vistas, in stg_dec__lean_tos' shape and for its reasons.
-- 134 rows, counted live 2026-08-27.
--
-- One of THREE DEC services that publish as `viewpoint` (the others are
-- stg_dec__firetowers and stg_dec__viewing_areas), because DEC splits by
-- asset type where lib/poi_schema.py's vocabulary splits by what a hiker
-- walks to. That is a mapping, not a merge: the three stay separate sources.
with source as (
    -- dlt lands geometry as GeoJSON text (extract/_kinds.py's JSON
    -- hint); cast here, as decision 40 has staging do.
    select
        -- The row's place in the raw table, which extract/_warehouse.py fills
        -- in the order the upstream served it: the order a Python exporter
        -- reads the same file in, and so its tie-break (see the poi_sources
        -- seed's file_order).
        rowid as source_row,
        * exclude (geometry),
        st_geomfromgeojson(cast(geometry as varchar)) as geom
    from {{ source('dec', 'raw_nysdec__dec_scenic_vistas') }}
),

renamed as (
    select
        {{ dbt_utils.generate_surrogate_key([
            "'dec_scenic_vistas'",
            'asset_uid',
        ]) }} as poi_key,
        source.*
    from source
)

{{ dbt_utils.deduplicate(
    relation='renamed', partition_by='poi_key', order_by='objectid'
) }}
