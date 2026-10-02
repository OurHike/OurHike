{{ config(materialized='table') }}
-- NYS Parks' temporary closed areas (stg_oprhp__trail_closures), as
-- export_nearby_trails.py's load_closure_areas() reads them for #964: one row
-- per area with a geometry that is not empty, its reason the layer's `Name`
-- and its place the layer's `Descript`, each stripped and null where blank
-- (sources.json's `reason_field` and `place_field`). A feature with no
-- geometry is skipped, as the Python skips it, rather than refused: it closes
-- nothing anyone could draw.
--
-- NO DATES ARE INVENTED. OPRHP publishes none per feature ("Closed Until
-- 2027" is prose inside the reason, not a field), so the closures mart
-- carries the reason verbatim and no start or end (CL13).
--
-- An empty layer is a good week, not a broken fetch: the registry's
-- `may_be_empty: true`, and no test here asserts a row count.
with areas as (
    select * from {{ ref('stg_oprhp__trail_closures') }}
)

select
    closure_key,
    nullif({{ python_strip('closure_reason') }}, '') as closure_reason,
    nullif({{ python_strip('closure_place') }}, '') as closure_place,
    cast(st_asgeojson(geom) as varchar) as geom_geojson,
    loaded_at as _loaded_at
from areas
where geom is not null and not st_isempty(geom)
