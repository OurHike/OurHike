-- NYS Parks has closed areas that may publish, and no network trail in the
-- trail_lines mart came out closed by one. Either every area misses every
-- published trail this week, which a layer can do, or the areas are in the
-- wrong place: a lon/lat swap in stg_oprhp__trail_closures took the
-- fixture's closed sections from 10 to 0 on a green build (measured
-- 2026-10-03). Warn, because the first case is real; the region-box test on
-- the closures mart is what fails the build on a swap.
{{ config(severity='warn') }}

with publication as (
    select source_key
    from {{ ref('int_sources__publication') }}
    where source_key = 'oprhp_trail_closures' and may_publish
),

areas as (
    select count(*) as area_count
    from {{ ref('int_closures__oprhp_areas') }}
    cross join publication
),

closed_sections as (
    select count(*) as section_count
    from {{ ref('trail_lines') }}
    where closure_kind = 'area'
)

select
    areas.area_count,
    closed_sections.section_count
from areas
cross join closed_sections
where areas.area_count > 0 and closed_sections.section_count = 0
