-- PO25, export_poi.py's fail_if_any_type_is_empty(): every type a
-- poi_<type>.geojson file is written for must hold at least one POI, bar
-- the ones the poi_types seed says may be empty (lib/poi_schema.py's
-- ALLOWED_EMPTY_POI_TYPES: trailhead, whose 7,358 USFS trailheads ship as
-- parking, #1218). A source that silently returns nothing after an upstream
-- schema change is otherwise indistinguishable from a deliberate absence,
-- and ships. Counted from the types rather than from the rows, so a type
-- that vanished entirely counts 0 instead of not appearing. Fails by
-- returning each empty type.
with types as (
    select * from {{ ref('poi_types') }}
    where
        state = 'published'
        and not may_be_empty
),

counts as (
    select
        poi_type,
        count(*) as pois
    from {{ ref('points_of_interest') }}
    where phone_files = 'poi_by_type'
    group by poi_type
)

select
    types.poi_type,
    coalesce(counts.pois, 0) as pois
from types
left join counts on types.poi_type = counts.poi_type
where coalesce(counts.pois, 0) < 1
