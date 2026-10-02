-- The A.T. centerline, one row per ATC segment: its attributes (surface,
-- status, the club acronym) and, since stage 3 of #1793, its geometry.
-- The geometry used to stay in the Python (DBT.md's scope line); the
-- trail_lines family reads it now, for the mile axis
-- (int_trail_lines__mile_axis) and the published lines.
with source as (
    -- dlt lands geometry as GeoJSON text (extract/_kinds.py's JSON
    -- hint); cast here, as decision 40 has staging do.
    --
    -- `rowid` is the row's place in the raw table. extract/_warehouse.py
    -- fills that table in the order the ArcGIS pages served the features,
    -- which is the order fetch_all.py wrote data/raw/centerline.geojson and
    -- the order export_elevation.py hands the segments to ST_Union_Agg
    -- (Reasoned from both files; @unvalidated across a load dlt splits into
    -- more than one file, which no fixture or fetch here has done). The
    -- extract lands no `_row` for an ArcGIS layer yet, and the merge's
    -- output depends on its input order.
    select
        rowid as source_row,
        * exclude (geometry),
        st_geomfromgeojson(cast(geometry as varchar)) as geom
    from {{ source('atc', 'raw_atc__centerline') }}
),

renamed as (
    select
        {{ dbt_utils.generate_surrogate_key([
            "'centerline'",
            'globalid',
        ]) }} as trail_segment_key,
        cast(globalid as varchar) as source_id,
        name,
        status,
        surface,
        reg_acro as region_acronym,
        acronym as club_acronym,
        length_ft,
        geom,
        source_row,
        _loaded_at as loaded_at
    from source
)

{{ dbt_utils.deduplicate(
    relation='renamed', partition_by='trail_segment_key', order_by='source_id'
) }}
