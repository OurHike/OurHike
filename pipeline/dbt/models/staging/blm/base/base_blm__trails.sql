-- BLM trails and routes (Natl GTLF public display) (BLM, sources.json
-- `blm_trails`): every row, keyed and deduped (decision 40), with nothing
-- filtered and nothing joined. A base model, the one place this dataset is
-- staged (decision 34), for the stewardship and staging models of every club
-- whose portion it holds.
--
-- Key: geometry plus five route columns, 19,530 of 19,530 live rows after 2
-- exact copies. @unvalidated until BLM says whether rows sharing a shape are
-- separate routes (pipeline/ELT.md, "One key per table", measured 2026-10-01).
--
-- The copies differ only in OBJECTID (duplicates_are_exact sets it aside),
-- and int_trail_lines__network_judged publishes the survivor's OBJECTID as
-- its trail_line_id, so the lowest survives: ordered by dlt's `_dlt_id`,
-- minted at random each load, the same rows could publish another id each
-- month (the review of PR #1805 — dlt → dbt re-platform as one go/no-go
-- change, 2026-10-05). DEC's models order by it the same way.
with source as (
    -- dlt lands geometry as GeoJSON text (extract/_kinds.py's JSON
    -- hint); cast here, as decision 40 has staging do.
    select
        * exclude (geometry),
        st_geomfromgeojson(cast(geometry as varchar)) as geom
    from {{ source('blm', 'raw_blm__blm_trails') }}
),

renamed as (
    select
        {{ dbt_utils.generate_surrogate_key([
            "'blm_trails'",
            geometry_key('geom'),
            'blm_miles',
            'route_plan_id',
            'def_fet2',
            'plan_season_rstrct_code',
            'route_prmry_nm',
        ]) }} as trail_segment_key,
        source.*
    from source
)

{{ dbt_utils.deduplicate(
    relation='renamed', partition_by='trail_segment_key', order_by='objectid'
) }}
