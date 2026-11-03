-- Mountains-to-Sea Trail (NC state-published layer) (NC State Parks,
-- sources.json `nc_mst_trail`): every row, keyed and deduped,
-- with nothing filtered and nothing joined. A base model, the one place this
-- dataset is staged, for the stewardship and staging models of
-- every club whose portion it holds.
--
-- Key: TRAILNAME and geometry, 328 of 328 live rows; Section with TRAILNAME is
-- 126 of 328 (pipeline/ELT.md, "One key per table", measured 2026-10-01).
with source as (
    -- dlt lands geometry as GeoJSON text (extract/_kinds.py's JSON
    -- hint); cast here, as staging models do.
    select
        * exclude (geometry),
        st_geomfromgeojson(cast(geometry as varchar)) as geom
    from {{ source('nc_mst', 'raw_nc_mst__nc_mst_trail') }}
),

renamed as (
    select
        {{ dbt_utils.generate_surrogate_key([
            "'nc_mst_trail'",
            'trailname',
            geometry_key('geom'),
        ]) }} as trail_segment_key,
        source.*
    from source
)

{{ dbt_utils.deduplicate(
    relation='renamed', partition_by='trail_segment_key', order_by='_dlt_id'
) }}
