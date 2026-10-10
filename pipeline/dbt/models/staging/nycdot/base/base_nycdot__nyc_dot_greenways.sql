-- NYC DOT Greenways (current, off-street) (NYC DOT, sources.json
-- `nyc_dot_greenways`): every row, keyed and deduped (decision 40), with
-- nothing filtered and nothing joined. A base model, the one place this
-- dataset is staged (decision 34), for the stewardship and staging models of
-- every club whose portion it holds.
--
-- Key: segmentid, 2,995 of 2,995 live rows after 44 exact copies: every
-- repeated segmentid was a repeated record (pipeline/ELT.md, "One key per
-- table", measured 2026-10-01). Re-measured 2026-10-03 on the landed table:
-- 3,039 rows, 10 segmentids repeated across 54 of them, all Bruckner
-- Boulevard segments in the Bronx (gwyjuris DOT), each repeated 2 to 10
-- times. The copies differ in nothing but Socrata's row id (`_socrata_id`)
-- and dlt's `_dlt_id`, so one line is drawn where the portal lists it up to
-- ten times. The lowest `_socrata_id` survives, so the same upstream rows
-- always keep the same id; a whole-dataset replace mints every `:id` again
-- (ELT.md, "Stable upstream keys"), which this does not change.
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
    relation='renamed', partition_by='trail_segment_key', order_by='_socrata_id'
) }}
