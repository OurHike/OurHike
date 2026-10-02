-- ATC's official A.T. Community towns, in stg_atc__shelters' shape and for
-- its reasons. A town is a resupply PROXY, which is why export_poi.py
-- publishes it at confidence 'low' where the facility layers carry 'high';
-- that call is the poi_type_mapping seed's `communities` row, joined in
-- int_points_of_interest__classified, not a literal here.
--
-- Upstream spells the name column NAME, not the facilities family's Name.
-- dlt lowercases both to `name`, so the poi_sources seed still names the
-- field export_poi.py's field map reads, NAME.
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
    from {{ source('atc', 'raw_atc__communities') }}
),

renamed as (
    select
        {{ dbt_utils.generate_surrogate_key([
            "'communities'",
            'globalid',
        ]) }} as poi_key,
        source.*
    from source
)

{{ dbt_utils.deduplicate(
    relation='renamed', partition_by='poi_key', order_by='_dlt_id'
) }}
