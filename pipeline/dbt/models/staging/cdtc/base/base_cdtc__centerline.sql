-- Continental Divide National Scenic Trail (CDTC) (CDTC, sources.json
-- `cdtc_centerline`): every row, keyed and deduped, with nothing
-- filtered and nothing joined. A base model, the one place this dataset is
-- staged, for the stewardship and staging models of every club
-- whose portion it holds.
--
-- Key: STATE, 8 of 8 live rows, one row per state (pipeline/ELT.md, "One key
-- per table", measured 2026-10-01).
with source as (
    -- dlt lands geometry as GeoJSON text (extract/_kinds.py's JSON
    -- hint); cast here, as staging models do.
    select
        * exclude (geometry),
        st_geomfromgeojson(cast(geometry as varchar)) as geom
    from {{ source('cdtc', 'raw_cdtc__cdtc_centerline') }}
),

renamed as (
    select
        {{ dbt_utils.generate_surrogate_key([
            "'cdtc_centerline'",
            'state',
        ]) }} as trail_segment_key,
        source.*
    from source
)

{{ dbt_utils.deduplicate(
    relation='renamed', partition_by='trail_segment_key', order_by='_dlt_id'
) }}
