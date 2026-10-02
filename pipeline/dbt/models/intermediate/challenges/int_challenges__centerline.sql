-- INTERFACE: replace with the trail_lines family's trail_lines mart (wk/tl-at)
--
-- The A.T. centerline every challenge place is measured against (CH04,
-- CH13), as export_challenges.load_centerline() reads it: the features of
-- trails.geojson whose `source` is `centerline` (export_trails.py's merged
-- chains, CENTERLINE_SOURCE), LineString or MultiLineString. Not a side
-- trail: a place beside a side trail is not a place on the A.T.
--
-- THE INTERFACE, one row per published centerline chain:
-- - trail_line_id: its published `id` (`centerline:chain:<n>`);
-- - geom_geojson: its geometry as trails.geojson prints it, RFC 7946 in
--   lon/lat. dbt's writer cuts coordinates to 6 places where export_trails.py
--   prints every digit (decision 8, at most 0.056 m), which is the
--   difference the trail_lines family's parity already lists.
--
-- At integration, with wk/tl-at's mart in the build, this body is (with
-- <ref('trail_lines')> written as a Jinja expression; braces are left out
-- here because a comment is rendered too):
--
--     select trail_line_id, geom_geojson
--     from <ref('trail_lines')>
--     where line_kind = 'centerline'
--
-- Until then it has no rows, so the distance check is skipped, which
-- export_challenges.py also does with no centerline, and says so: the test
-- challenges_distance_check_has_a_centerline_to_measure_against warns. It
-- reads ATC's centerline staging only so that it is not a root model.
select
    cast(null as varchar) as trail_line_id,
    cast(null as varchar) as geom_geojson
from {{ ref('stg_atc__centerline_segments') }}
where false
