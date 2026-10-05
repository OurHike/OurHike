-- Alaska Trail Database (Alaska Trails, sources.json `alaska_trails`): every
-- row, keyed and deduped (decision 40), with nothing filtered and nothing
-- joined. A base model, the one place this dataset is staged (decision 34),
-- for the stewardship and staging models of every club whose portion it holds.
--
-- Key: TrailName, TrailType and geometry, 1,595 of 1,595 live rows after 7
-- exact copies; TrailType is null on 126, and without it one line carries two
-- named trails (pipeline/ELT.md, "One key per table", measured 2026-10-01).
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
    from {{ source('alaska_trails', 'raw_alaska_trails__alaska_trails') }}
),

renamed as (
    select
        {{ dbt_utils.generate_surrogate_key([
            "'alaska_trails'",
            'trailname',
            'trailtype',
            geometry_key('geom'),
        ]) }} as trail_segment_key,
        source.*
    from source
)

{{ dbt_utils.deduplicate(
    relation='renamed', partition_by='trail_segment_key', order_by='objectid'
) }}
