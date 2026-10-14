-- The areas that may place a notice's point (int_closures__club_notices'
-- rule 4): one row per notice source seeds/notice_steward_areas.csv links to
-- a layer of its own steward's areas, and per area of that layer, carrying
-- the area's own outline as GeoJSON text. The maintainer's answer to Q3
-- (poll of 2026-10-11, decision 185): "a status point inside exactly one of
-- its steward's own areas takes that area". Which source names which layer
-- is the seed's, never a key written here, so the rule is the same for
-- every steward.
--
-- AN AREA PLACES A POINT ONLY WHERE NOTHING ABOUT IT IS IN DOUBT:
-- - Its layer may publish itself (int_sources__publication's may_publish).
--   The outline reaches a phone as the place of another source's notice, so
--   it must never outrun its own licence or its own reaches_hikers
--   (CLAUDE.md, "Never let a display outrun its source"). A layer held back
--   places nothing.
-- - Its key is held by one raw row (`key_versions` 1). Two different
--   outlines under one key are a conflict the dedupe settles by keeping one
--   of them (decision 40 allows only exact copies), so neither places
--   anything.
-- - It is an area: its GeoJSON's own `type` is Polygon or MultiPolygon. A
--   line or a point in an areas layer has nothing inside it.
-- None of these drops a notice: a point no area here may place keeps its own
-- geometry in int_closures__club_notices, as a point inside none does.
with links as (
    select * from {{ ref('notice_steward_areas') }}
),

areas as (
    select * from {{ ref('int_closures__steward_areas_unioned') }}
),

publication as (
    select * from {{ ref('int_sources__publication') }}
)

select
    {{ dbt_utils.generate_surrogate_key([
        'links.source_key', 'areas.area_key'
    ]) }} as steward_area_key,
    links.source_key,
    areas.source_key as areas_source_key,
    areas.area_key,
    areas.area_id,
    areas.geom_geojson
from links
inner join areas on links.areas_source_key = areas.source_key
inner join publication on areas.source_key = publication.source_key
where
    publication.may_publish
    and areas.key_versions = 1
    and json_extract_string(areas.geom_geojson, '$.type')
    in ('Polygon', 'MultiPolygon')
