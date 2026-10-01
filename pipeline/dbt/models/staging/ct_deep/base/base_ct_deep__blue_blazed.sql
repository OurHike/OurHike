-- Connecticut Blue-Blazed Hiking Trails (CT DEEP, sources.json
-- `ct_deep_blue_blazed`): every row, keyed and deduped (decision 40), with
-- nothing filtered and nothing joined. A base model, the one place this
-- dataset is staged (decision 34), for the stewardship and staging models of
-- every club whose portion it holds.
--
-- Key: TrailName, Par_Name and geometry, 351 of 351 live rows; TrailName with
-- Par_Name alone is 350 of 351 (pipeline/ELT.md, "One key per table", measured
-- 2026-10-01).
with source as (
    -- dlt lands geometry as GeoJSON text (extract/_kinds.py's JSON
    -- hint); cast here, as decision 40 has staging do.
    select
        * exclude (geometry),
        st_geomfromgeojson(cast(geometry as varchar)) as geom
    from {{ source('ct_deep', 'raw_ct_deep__ct_deep_blue_blazed') }}
),

renamed as (
    select
        {{ dbt_utils.generate_surrogate_key([
            "'ct_deep_blue_blazed'",
            'trailname',
            'par_name',
            geometry_key('geom'),
        ]) }} as trail_segment_key,
        source.*
    from source
)

{{ dbt_utils.deduplicate(
    relation='renamed', partition_by='trail_segment_key', order_by='_dlt_id'
) }}
