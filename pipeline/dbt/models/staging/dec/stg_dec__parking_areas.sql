-- DEC's parking areas, in stg_dec__lean_tos' shape and for its reasons.
-- 1,852 rows, counted live 2026-08-27. One ASSET_UID names two lots that
-- differ only by place (measured 2026-10-01), so the key adds the geometry.
--
-- NO SEASONAL ACCESS COLUMN, and that absence is measured rather than
-- assumed: sources.json read one sampled row carrying 'SEASONALLY OPEN MAY 1
-- TO SEPT 30' in free-text NOTES, so seasonality exists in DEC's data as
-- PROSE and not as a field. A model that invented an `open_seasonally`
-- column would be answering a question DEC has not answered.
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
    from {{ source('dec', 'raw_nysdec__dec_parking_areas') }}
),

renamed as (
    select
        {{ dbt_utils.generate_surrogate_key([
            "'dec_parking_areas'",
            'asset_uid',
            geometry_key('geom'),
        ]) }} as poi_key,
        source.*
    from source
)

{{ dbt_utils.deduplicate(
    relation='renamed', partition_by='poi_key', order_by='objectid'
) }}
