-- The blue blazes' attribute record. export_spurs.py owns the published
-- artifact; this is where the raw Blaze vocabulary is staged for
-- features/TRAIL_BLAZE_COLORS.md's normalisation to build on - including
-- the real dirt that document names (24 features with no value, literal
-- "Unknown", "Gold"), which is exactly why the column carries no
-- accepted_values test yet: the domain is the finding, not a constraint.
with source as (
    -- dlt lands geometry as GeoJSON text (extract/_kinds.py's JSON
    -- hint); cast here, as decision 40 has staging do.
    select
        * exclude (geometry),
        st_geomfromgeojson(cast(geometry as varchar)) as geom
    from {{ source('atc', 'raw_atc__side_trails') }}
),

renamed as (
    select
        {{ dbt_utils.generate_surrogate_key([
            "'side_trails'",
            'globalid',
        ]) }} as trail_segment_key,
        cast(globalid as varchar) as source_id,
        name,
        status,
        type as trail_type,
        blaze,
        length_ft,
        _loaded_at as loaded_at
    from source
)

{{ dbt_utils.deduplicate(
    relation='renamed', partition_by='trail_segment_key', order_by='source_id'
) }}
