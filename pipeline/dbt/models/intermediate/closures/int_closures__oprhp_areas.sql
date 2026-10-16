-- NYS Parks' temporary closed areas (stg_oprhp__trail_closures), as
-- export_nearby_trails.py's load_closure_areas() reads them for #964: one row
-- per area with a geometry that is not empty, its reason the layer's `Name`
-- and its place the layer's `Descript`, each stripped and null where blank
-- (sources.json's `reason_field` and `place_field`). A feature with no
-- geometry is skipped, as the Python skips it, rather than refused: it closes
-- nothing anyone could draw.
--
-- NO DATES ARE INVENTED. OPRHP publishes none per feature, so the closures
-- mart carries the reason verbatim and no start. ITS END IS THE ONE
-- ITS OWN REASON STATES, read as every source's title is (rule
-- 13; macros/notice_title_end_day.sql): "Closed Until 2027 due to
-- construction" ends on 2027-12-31, a year alone read to its last day, so
-- the phone says "Its source said it would end December 31, 2027" where it
-- said "Its source gives no date" (UA's notices.json of 2026-10-15 21:26
-- UTC, the one OPRHP area whose reason states an end). A reason that states
-- none leaves the end null.
--
-- An empty layer is a good week, not a broken fetch: the registry's
-- `may_be_empty: true`, and no test here asserts a row count.
with areas as (
    select * from {{ ref('stg_oprhp__trail_closures') }}
)

select
    closure_key,
    -- The area's place in the layer, which breaks apply_area_closures()' tie
    -- (int_trail_lines__network_area_closures).
    source_row,
    nullif({{ python_strip('closure_reason') }}, '') as closure_reason,
    nullif({{ python_strip('closure_place') }}, '') as closure_place,
    {{ notice_title_end_day('closure_reason') }} as ends_on,
    cast(st_asgeojson(geom) as varchar) as geom_geojson,
    loaded_at as _loaded_at
from areas
where geom is not null and not st_isempty(geom)
