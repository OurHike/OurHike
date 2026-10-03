-- NYC Parks Drinking Fountains (outdoor types) (NYC Parks, sources.json
-- `nyc_drinking_fountains`): every row, keyed and deduped (decision 40), with
-- nothing filtered and nothing joined. A base model, the one place this
-- dataset is staged (decision 34), for the stewardship and staging models of
-- every club whose portion it holds.
--
-- Key: system and gispropnum, unique on 3,195 live rows (pipeline/ELT.md, "One
-- key per table", measured 2026-10-01).
with source as (
    -- dlt lands geometry as GeoJSON text (extract/_kinds.py's JSON
    -- hint); cast here, as decision 40 has staging do.
    select
        * exclude (geometry),
        st_geomfromgeojson(cast(geometry as varchar)) as geom
    from {{ source('nycparks', 'raw_nycparks__nyc_drinking_fountains') }}
),

renamed as (
    select
        {{ dbt_utils.generate_surrogate_key([
            "'nyc_drinking_fountains'",
            '"system"',
            'gispropnum',
        ]) }} as poi_key,
        source.*
    from source
)

-- Copies may differ in Socrata's row id, which is this POI's published id
-- (the registry's `id_field` is `:id`), so the lowest one survives
-- (macros/duckdb__deduplicate.sql). 0 copies on 3,195 live rows, 2026-10-03.
{{ dbt_utils.deduplicate(
    relation='renamed', partition_by='poi_key', order_by='_socrata_id'
) }}
