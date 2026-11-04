-- NYC Public Restrooms (operational) (NYC Parks, sources.json
-- `nyc_public_restrooms`): every row, keyed and deduped, with
-- nothing filtered and nothing joined. A base model, the one place this
-- dataset is staged, for the stewardship and staging models of
-- every club whose portion it holds.
--
-- Key: geometry, 973 of 973 live rows after 2 exact copies (pipeline/ELT.md,
-- "One key per table", measured 2026-10-01). Re-measured 2026-10-03 on the
-- landed table: 975 rows, and the two restrooms listed twice are the ones
-- named Ancient Playground and Heckscher Playground (operator NYC Parks).
-- Each pair has the same point and the same value in every published column,
-- and differs in nothing but Socrata's row id (`_socrata_id`) and dlt's
-- `_dlt_id`, so keeping one copy loses no restroom a hiker could find. The
-- lowest `_socrata_id` survives: it is the POI's published id (the registry's
-- `id_field` is `:id`), and it is the copy parity.py's _exact_copy_reasons
-- expects kept.
--
-- Key: geometry and facility_name since #1976. Measured live 2026-11-04:
-- 998 rows at 994 points. Carl Schurz Main Lawn and Catbird Playground are
-- two restrooms at one point, so the point alone would drop one; with the
-- name, 995 keys. The 3 repeated keys are Tompkins Square Park, Heckscher
-- Playground and Ancient Playground, each listed twice, the copies differing
-- only in `changing_stations` (blank on one, Yes on the other), which
-- duplicates_are_exact leaves out (`skip_columns`). No model reads that
-- column, so the copy kept, the lowest `_socrata_id` as before, loses
-- nothing a hiker sees; a model that reads it must revisit this.
with source as (
    -- dlt lands geometry as GeoJSON text (extract/_kinds.py's JSON
    -- hint); cast here, as staging models do.
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
            'facility_name',
        ]) }} as poi_key,
        source.*
    from source
)

{{ dbt_utils.deduplicate(
    relation='renamed', partition_by='poi_key', order_by='_socrata_id'
) }}
