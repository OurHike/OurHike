-- DEC's back-country asset inventory as the extract lands it, keyed and
-- deduplicated (decision 40), every column kept.
--
-- THIS IS NOT A POI LAYER, and the name invites the opposite reading. DEC's
-- own description calls it "point data locating and differentiating assets
-- on state lands... man-made items, which require periodic maintenance or
-- inspection". 21,468 points counted live 2026-08-27; the largest single
-- value is CULVERT at 4,290 features, and sources.json records that 68% of
-- the layer is things no hiker wants a pin for. So the entry declares no
-- `poi_type`, and what publishes from it does so row by row, through
-- export_nearby_poi.py's DEC_ASSET_TYPES allowlist (privies only, since #1674
-- withdrew the crossings) and the PUBLICUSE flag. Both are applied in
-- int_points_of_interest__classified, from the poi_value_types seed.
--
-- `asset` IS FREE TEXT AND IT IS DIRTY: 234 values as stored, 223 after
-- trimming, including 'FORD ' beside 'FORD', a bare ' ' on 86 rows, and
-- DEC's own misspellings ('PRIMATIVE CAMPSITE'). Every match on it is
-- case-insensitive and stripped, as export_nearby_poi.py's is.
--
-- ASSET_UID and the geometry leave one pair at one place under two names
-- (measured 2026-10-01), so the key adds NAME.
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
    from {{ source('dec', 'raw_nysdec__dec_backcountry_features') }}
),

renamed as (
    select
        {{ dbt_utils.generate_surrogate_key([
            "'dec_backcountry_features'",
            'asset_uid',
            'name',
            geometry_key('geom'),
        ]) }} as poi_key,
        source.*
    from source
)

{{ dbt_utils.deduplicate(
    relation='renamed', partition_by='poi_key', order_by='objectid'
) }}
