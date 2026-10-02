-- The blue blazes' attribute record. export_spurs.py owns the published
-- artifact; this is where the raw Blaze vocabulary is staged for
-- features/TRAIL_BLAZE_COLORS.md's normalisation to build on - including
-- the real dirt that document names (24 features with no value, literal
-- "Unknown", "Gold"), which is exactly why the column carries no
-- accepted_values test yet: the domain is the finding, not a constraint.
--
-- Since stage 3 of #1793 it carries the geometry and the row's place in the
-- layer too, for the trail_lines family's side trails and spurs, as
-- stg_atc__centerline_segments does for the centerline.
with source as (
    -- dlt lands geometry as GeoJSON text (extract/_kinds.py's JSON
    -- hint); cast here, as decision 40 has staging do.
    --
    -- `rowid` is the row's place in the raw table, the order the ArcGIS
    -- pages served the features and fetch_all.py wrote
    -- data/raw/side_trails.geojson (stg_atc__centerline_segments says why,
    -- and where that is @unvalidated). export_trails.py numbers a feature
    -- with no id by that place, and writes the side trails in it.
    select
        rowid as source_row,
        * exclude (geometry),
        st_geomfromgeojson(cast(geometry as varchar)) as geom
    from {{ source('atc', 'raw_atc__side_trails') }}
),

-- The key is the GlobalID, or the OBJECTID where a row has none. GlobalID
-- alone would give every row without one the same key, and the dedupe would
-- keep one of them, where lib/feature_id.py publishes each under the
-- feature's own id, which on an ArcGIS layer is its OBJECTID. None has
-- arrived without one (1,197 of 1,197 live features carry a GlobalID,
-- 2026-10-02), and the not_null test on source_id says so at warn the day
-- one does.
renamed as (
    select
        {{ dbt_utils.generate_surrogate_key([
            "'side_trails'",
            "coalesce(globalid, cast(objectid as varchar))",
        ]) }} as trail_segment_key,
        cast(globalid as varchar) as source_id,
        objectid,
        name,
        status,
        type as trail_type,
        blaze,
        length_ft,
        geom,
        source_row,
        _loaded_at as loaded_at
    from source
)

{{ dbt_utils.deduplicate(
    relation='renamed', partition_by='trail_segment_key', order_by='source_id'
) }}
