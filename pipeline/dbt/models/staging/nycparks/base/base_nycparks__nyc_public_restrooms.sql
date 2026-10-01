-- NYC Public Restrooms (operational) (NYC Parks, sources.json
-- `nyc_public_restrooms`): every row, keyed and deduped (decision 40), with
-- nothing filtered and nothing joined. A base model, the one place this
-- dataset is staged (decision 34), for the stewardship and staging models of
-- every club whose portion it holds.
--
-- Key: geometry, 973 of 973 live rows after 2 exact copies (pipeline/ELT.md,
-- "One key per table", measured 2026-10-01).
with source as (
    -- dlt lands geometry as GeoJSON text (extract/_kinds.py's JSON
    -- hint); cast here, as decision 40 has staging do.
    select
        * exclude (geometry),
        st_geomfromgeojson(cast(geometry as varchar)) as geom
    from {{ source('nycparks', 'raw_nycparks__nyc_public_restrooms') }}
),

renamed as (
    select
        {{ dbt_utils.generate_surrogate_key([
            "'nyc_public_restrooms'",
            geometry_key('geom'),
        ]) }} as poi_key,
        source.*
    from source
)

{{ dbt_utils.deduplicate(
    relation='renamed', partition_by='poi_key', order_by='_dlt_id'
) }}
