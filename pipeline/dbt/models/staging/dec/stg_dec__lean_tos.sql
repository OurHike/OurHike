-- DEC's lean-tos as the extract lands them (extract/nysdec/
-- points_of_interest.py), keyed and deduplicated (decision 40), with every
-- upstream column kept. The other five DEC per-type POI models have this
-- shape and refer here.
--
-- WHAT A ROW IS STAYS OUT OF STAGING, as decision 40 asks. sources.json
-- declares this layer's poi_type ('shelter'), its id field (OBJECTID), its
-- name field (NAME), its public flag (PUBLICUSE = 'Y') and the asset and
-- facility fields a description is composed from; export_nearby_poi.py reads
-- them from there, and so does int_points_of_interest__classified, which
-- also applies the flag. The confidence ('high') is what that module's
-- public_verdict() gives a kept DEC row, held by tests/test_dbt_seed_sync.py.
--
-- NO CAPACITY COLUMN, because the layer has none. sources.json's measurement
-- is explicit: "nothing states how many the shelter sleeps, so a DEC shelter
-- exports without capacity - absent meaning unknown, never zero".
--
-- The whole field list was measured live 2026-08-27 (315 rows statewide).
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
    from {{ source('dec', 'raw_nysdec__dec_lean_tos') }}
),

renamed as (
    select
        {{ dbt_utils.generate_surrogate_key([
            "'dec_lean_tos'",
            'asset_uid',
        ]) }} as poi_key,
        source.*
    from source
)

{{ dbt_utils.deduplicate(
    relation='renamed', partition_by='poi_key', order_by='objectid'
) }}
