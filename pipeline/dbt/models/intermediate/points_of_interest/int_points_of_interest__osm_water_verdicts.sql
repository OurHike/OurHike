{{ config(materialized='table') }}
-- Every corridor OSM water point's verdict (PO06): the distance pass,
-- int_points_of_interest__osm_water_reach, beside the grade
-- step_osm_water_grade took for it, as build_osm_water_reach.py's verdict
-- file holds both halves in one record. `reachable` is the step's, both
-- gates with an ungraded point not reachable; it is null only where the step
-- wrote no verdict for a point the distance pass holds, which
-- assert_every_corridor_osm_water_point_has_a_verdict fails the build on and
-- int_points_of_interest__reached reads as not reachable. The reason is the
-- grade's where it has one, else the distance pass's, as apply_grade_gate()
-- leaves the record.
with reach as (
    select * from {{ ref('int_points_of_interest__osm_water_reach') }}
),

grades as (
    select * from {{ ref('stg_derived__osm_water_grade') }}
)

select
    reach.poi_key,
    reach.osm_id,
    reach.nearest,
    reach.nearest_source,
    reach.passes_distance,
    grades.passes_grade,
    grades.grade_floored,
    grades.osm_id is not null as has_verdict,
    grades.reachable,
    coalesce(grades.reason, reach.reason) as reason
from reach
left join grades on reach.osm_id = grades.osm_id
