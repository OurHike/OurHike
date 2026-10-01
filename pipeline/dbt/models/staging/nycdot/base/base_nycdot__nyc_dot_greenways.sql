-- NYC DOT Greenways (current, off-street) (NYC DOT, sources.json
-- `nyc_dot_greenways`): every row, keyed and deduped (decision 40), with
-- nothing filtered and nothing joined. A base model, the one place this
-- dataset is staged (decision 34), for the stewardship and staging models of
-- every club whose portion it holds.
--
-- Key: segmentid, 2,995 of 2,995 live rows after 44 exact copies: every
-- repeated segmentid was a repeated record (pipeline/ELT.md, "One key per
-- table", measured 2026-10-01).
with source as (
    -- dlt lands geometry as GeoJSON text (extract/_kinds.py's JSON
    -- hint); cast here, as decision 40 has staging do.
    select
        * exclude (geometry),
        st_geomfromgeojson(cast(geometry as varchar)) as geom
    from {{ source('nycdot', 'raw_nycdot__nyc_dot_greenways') }}
),

renamed as (
    select
        {{ dbt_utils.generate_surrogate_key([
            "'nyc_dot_greenways'",
            'segmentid',
        ]) }} as trail_segment_key,
        source.*
    from source
)

{{ dbt_utils.deduplicate(
    relation='renamed', partition_by='trail_segment_key', order_by='_dlt_id'
) }}
