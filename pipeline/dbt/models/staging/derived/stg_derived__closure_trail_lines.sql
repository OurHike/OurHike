-- The release's trail lines that may run inside an area closure, the A.T.'s
-- own among them: step_closure_trail_lines's table
-- (pipeline/step_closure_trail_lines.py), staged like any table a source
-- lands. int_closures__area_trail_cuts cuts them against each area.
--
-- Key: the release and the line's id, which is unique on every one of UA's
-- release 2026-10-10-2's 364,668 nearby trail lines (Measured 2026-10-11)
-- and on every one of its 1,659 trails.geojson lines (Measured 2026-10-14),
-- and which prepare_closure_trail_lines.py writes once per line across both
-- files, whatever the release holds.
with source as (
    -- The step writes the line as GeoJSON text, as dlt lands every
    -- geometry; cast here, as staging models do.
    select
        * exclude (geometry),
        st_geomfromgeojson(cast(geometry as varchar)) as geom
    from {{ source('derived', 'closure_trail_lines') }}
),

renamed as (
    select
        {{ dbt_utils.generate_surrogate_key([
            "'closure_trail_lines'",
            'release',
            'line_id',
        ]) }} as closure_trail_line_key,
        release,
        line_id,
        geom,
        _loaded_at as loaded_at
    from source
)

{{ dbt_utils.deduplicate(
    relation='renamed', partition_by='closure_trail_line_key', order_by='line_id'
) }}
