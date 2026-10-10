-- NYC Street Centerline - pedestrian ways (path, boardwalk, step street,
-- non-vehicular) (NYC DOT, sources.json `nyc_cscl_paths`): every row, keyed
-- and deduped (decision 40), with nothing filtered and nothing joined. A base
-- model, the one place this dataset is staged (decision 34), for the
-- stewardship and staging models of every club whose portion it holds.
--
-- Key: globalid unique on 6,496 of 6,496 live rows (pipeline/ELT.md, "One key
-- per table", measured 2026-10-01).
with source as (
    -- dlt lands geometry as GeoJSON text (extract/_kinds.py's JSON
    -- hint); cast here, as decision 40 has staging do.
    select
        * exclude (geometry),
        st_geomfromgeojson(cast(geometry as varchar)) as geom
    from {{ source('nycdot', 'raw_nycdot__nyc_cscl_paths') }}
),

renamed as (
    select
        {{ dbt_utils.generate_surrogate_key([
            "'nyc_cscl_paths'",
            'globalid',
        ]) }} as trail_segment_key,
        source.*
    from source
)

-- Copies may differ in Socrata's row id, so the lowest one survives, as in
-- every NYC Socrata base model (macros/duckdb__deduplicate.sql).
{{ dbt_utils.deduplicate(
    relation='renamed', partition_by='trail_segment_key', order_by='_socrata_id'
) }}
