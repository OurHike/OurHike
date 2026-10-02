-- DEC's firetowers, in stg_dec__lean_tos' shape and for its reasons. 35
-- rows, counted live 2026-08-27. sources.json types the layer `viewpoint`.
--
-- @unvalidated - that type carries its own caveat, repeated here because a
-- staging model is where a consumer will actually look: a restored tower is
-- a thing hikers climb for the view, but a hiker who reaches a CLOSED one
-- finds a locked cab, and this layer publishes no open/closed state to tell
-- them apart. What would settle it is DEC's own tower-status list, which is
-- prose on their website rather than a field here. Nothing in this model may
-- be read as "the tower is climbable".
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
    from {{ source('dec', 'raw_nysdec__dec_firetowers') }}
),

renamed as (
    select
        {{ dbt_utils.generate_surrogate_key([
            "'dec_firetowers'",
            'asset_uid',
        ]) }} as poi_key,
        source.*
    from source
)

{{ dbt_utils.deduplicate(
    relation='renamed', partition_by='poi_key', order_by='objectid'
) }}
