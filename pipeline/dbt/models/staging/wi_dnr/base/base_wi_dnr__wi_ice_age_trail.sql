-- Ice Age National Scenic Trail in Wisconsin (WDNR) (Wisconsin DNR,
-- sources.json `wi_ice_age_trail`): every row, keyed and deduped (decision
-- 40), with nothing filtered and nothing joined. A base model, the one place
-- this dataset is staged (decision 34), for the stewardship and staging models
-- of every club whose portion it holds.
--
-- Key: one live row, so the registry key alone is unique; the geometry is
-- added because a key needs a column beside the registry key, and a one-row
-- layer's shape is trivially unique (pipeline/ELT.md, "One key per table",
-- measured 2026-10-01).
with source as (
    -- dlt lands geometry as GeoJSON text (extract/_kinds.py's JSON
    -- hint); cast here, as decision 40 has staging do.
    select
        * exclude (geometry),
        st_geomfromgeojson(cast(geometry as varchar)) as geom
    from {{ source('wi_dnr', 'raw_wi_dnr__wi_ice_age_trail') }}
),

renamed as (
    select
        {{ dbt_utils.generate_surrogate_key([
            "'wi_ice_age_trail'",
            geometry_key('geom'),
        ]) }} as trail_segment_key,
        source.*
    from source
)

{{ dbt_utils.deduplicate(
    relation='renamed', partition_by='trail_segment_key', order_by='_dlt_id'
) }}
