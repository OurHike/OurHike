-- USFS Recreation Sites (INFRA, nationwide) (USFS, sources.json
-- `usfs_rec_sites`): every row, keyed and deduped (decision 40), with nothing
-- filtered and nothing joined. A base model, the one place this dataset is
-- staged (decision 34), for the stewardship and staging models of every club
-- whose portion it holds.
--
-- Key: globalid unique on 31,415 live rows (pipeline/ELT.md, "One key per
-- table", measured 2026-10-01).
with source as (
    -- dlt lands geometry as GeoJSON text (extract/_kinds.py's JSON
    -- hint); cast here, as decision 40 has staging do.
    select
        * exclude (geometry),
        st_geomfromgeojson(cast(geometry as varchar)) as geom
    from {{ source('usfs', 'raw_usfs__usfs_rec_sites') }}
),

renamed as (
    select
        {{ dbt_utils.generate_surrogate_key([
            "'usfs_rec_sites'",
            'globalid',
        ]) }} as poi_key,
        source.*
    from source
)

{{ dbt_utils.deduplicate(
    relation='renamed', partition_by='poi_key', order_by='_dlt_id'
) }}
