-- NYC Parks Properties (park boundaries) (NYC Parks, sources.json
-- `nyc_park_polygons`): every row, keyed and deduped (decision 40), with
-- nothing filtered and nothing joined. A base model, the one place this
-- dataset is staged (decision 34), for the stewardship and staging models of
-- every club whose portion it holds.
--
-- Key: gispropnum, the registry's `id_field`, unique and non-null on 2,061 of
-- 2,061 live rows (measured 2026-10-03; pipeline/ELT.md, "One key per table").
-- The key was `system` and gispropnum until the monthly lane's first live
-- build (refresh-reference.yml run 37109384156) failed on it: `system` is a
-- drinking-fountains column, and Socrata enfh-gkve declares 33 columns with no
-- `system` among them.
with source as (
    -- dlt lands geometry as GeoJSON text (extract/_kinds.py's JSON
    -- hint); cast here, as decision 40 has staging do.
    select
        * exclude (geometry),
        st_geomfromgeojson(cast(geometry as varchar)) as geom
    from {{ source('nycparks', 'raw_nycparks__nyc_park_polygons') }}
),

renamed as (
    select
        {{ dbt_utils.generate_surrogate_key([
            "'nyc_park_polygons'",
            'gispropnum',
        ]) }} as park_key,
        source.*
    from source
)

-- Copies may differ in Socrata's row id, so the lowest one survives, as in
-- every NYC Socrata base model (macros/duckdb__deduplicate.sql). 0 copies on
-- 2,061 live rows, 2026-10-03.
{{ dbt_utils.deduplicate(
    relation='renamed', partition_by='park_key', order_by='_socrata_id'
) }}
