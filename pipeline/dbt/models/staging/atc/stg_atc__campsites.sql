-- ATC's A.T. campsites, in stg_atc__shelters' shape and for its reasons:
-- keyed, deduplicated, every upstream column kept (the description reads
-- Type, Site_Num and the rest), and nothing said here about what a row is.
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
    from {{ source('atc', 'raw_atc__campsites') }}
),

renamed as (
    select
        {{ dbt_utils.generate_surrogate_key([
            "'campsites'",
            'globalid',
        ]) }} as poi_key,
        source.*
    from source
)

{{ dbt_utils.deduplicate(
    relation='renamed', partition_by='poi_key', order_by='_dlt_id'
) }}
