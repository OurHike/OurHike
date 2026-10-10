-- NYC Parks Trails (five boroughs) (NYC Parks, sources.json
-- `nyc_parks_trails`): every row, keyed and deduped (decision 40), with
-- nothing filtered and nothing joined. A base model, the one place this
-- dataset is staged (decision 34), for the stewardship and staging models of
-- every club whose portion it holds.
--
-- Key: geometry and date_collected, 7,055 of 7,055 live rows after 4 exact
-- copies; date_collected is null on 4 (pipeline/ELT.md, "One key per table",
-- measured 2026-10-01). Re-measured 2026-10-03 on the landed table: 7,059
-- rows, 4 keys held by 2 rows each, all Pelham Bay Park's 'Unnamed Official
-- Trail' segments surveyed 2015-05-05. Each pair differs in nothing but
-- Socrata's row id (`_socrata_id`) and dlt's `_dlt_id`. The lowest
-- `_socrata_id` survives, and it is the line's published id
-- (int_trail_lines__network_judged), so the same upstream rows always
-- publish the same id; a whole-dataset replace mints every `:id` again
-- (ELT.md, "Stable upstream keys").
with source as (
    -- dlt lands geometry as GeoJSON text (extract/_kinds.py's JSON
    -- hint); cast here, as decision 40 has staging do.
    select
        * exclude (geometry),
        st_geomfromgeojson(cast(geometry as varchar)) as geom
    from {{ source('nycparks', 'raw_nycparks__nyc_parks_trails') }}
),

renamed as (
    select
        {{ dbt_utils.generate_surrogate_key([
            "'nyc_parks_trails'",
            geometry_key('geom'),
            'date_collected',
        ]) }} as trail_segment_key,
        source.*
    from source
)

{{ dbt_utils.deduplicate(
    relation='renamed', partition_by='trail_segment_key', order_by='_socrata_id'
) }}
