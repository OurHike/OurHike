-- opentrail.org's A.T. waypoints as the extract lands them (extract/_shared/
-- opentrail/at.py), keyed and deduplicated (decision 40), every column kept.
--
-- The `icon` code is resolved to a poi_type downstream, not here: decision 40
-- moved this model's join to the poi_type_mapping seed into
-- int_points_of_interest__classified, so staging only renames, casts, keys
-- and dedupes. Every waypoint stays, whatever its icon, and the classifier
-- says which icons export_poi.py publishes (w and s, both as water).
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
    from {{ source('opentrail', 'raw_opentrail__at') }}
),

renamed as (
    select
        {{ dbt_utils.generate_surrogate_key([
            "'opentrail_at'",
            'dbid',
        ]) }} as poi_key,
        source.*
    from source
)

{{ dbt_utils.deduplicate(
    relation='renamed', partition_by='poi_key', order_by='_dlt_id'
) }}
