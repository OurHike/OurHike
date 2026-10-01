-- NJ State Park Service Trails (NJDEP Bureau of GIS, Features/Land layer 63)
-- (NJDEP, sources.json `njdep_park_trails`): every row, keyed and deduped
-- (decision 40), with nothing filtered and nothing joined. A base model, the
-- one place this dataset is staged (decision 34), for the stewardship and
-- staging models of every club whose portion it holds.
--
-- Key: GLOBALID unique on 3,305 live rows (pipeline/ELT.md, "One key per
-- table", measured 2026-10-01).
with source as (
    -- dlt lands geometry as GeoJSON text (extract/_kinds.py's JSON
    -- hint); cast here, as decision 40 has staging do.
    select
        * exclude (geometry),
        st_geomfromgeojson(cast(geometry as varchar)) as geom
    from {{ source('njgin', 'raw_njgin__njdep_park_trails') }}
),

renamed as (
    select
        {{ dbt_utils.generate_surrogate_key([
            "'njdep_park_trails'",
            'globalid',
        ]) }} as trail_segment_key,
        source.*
    from source
)

{{ dbt_utils.deduplicate(
    relation='renamed', partition_by='trail_segment_key', order_by='_dlt_id'
) }}
