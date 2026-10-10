-- DEC's primitive campsites, in stg_dec__lean_tos' shape and for its
-- reasons: keyed, deduplicated, every column kept, nothing classified.
--
-- 2,078 rows statewide, counted live 2026-08-27. These are BACKCOUNTRY sites
-- and one row is one tent site, which is the difference sources.json records
-- against OPRHP's campsite rows, where one row is a whole drive-in
-- campground. Nothing here encodes that difference.
--
-- ASSET_UID IS NOT UNIQUE HERE (2,088 of 2,093 on 2026-10-01): DEC gave four
-- ids to two different sites at two places, so the key adds the geometry,
-- and one record arrives twice exactly, which the dedupe removes. The lower
-- OBJECTID survives; export_nearby_poi.py publishes both copies.
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
    from {{ source('dec', 'raw_nysdec__dec_primitive_campsites') }}
),

renamed as (
    select
        {{ dbt_utils.generate_surrogate_key([
            "'dec_primitive_campsites'",
            'asset_uid',
            geometry_key('geom'),
        ]) }} as poi_key,
        source.*
    from source
)

{{ dbt_utils.deduplicate(
    relation='renamed', partition_by='poi_key', order_by='objectid'
) }}
