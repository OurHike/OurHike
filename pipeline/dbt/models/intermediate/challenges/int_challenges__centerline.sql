-- The A.T. centerline every challenge place is measured against (CH04,
-- CH13), as export_challenges.load_centerline() reads it: the features of
-- trails.geojson whose `source` is `centerline`, LineString or
-- MultiLineString. trails.geojson is the trail_lines mart's rows that are
-- not `network` or `club` (pub_trails_geojson), and it publishes source_key as
-- `source`, so this is those rows with source_key `centerline`: the A.T.'s
-- own chains. Not a side trail: a place beside a side trail is not a place
-- on the A.T.
--
-- The geometry is the mart's, cut to 6 decimals (decision 8), where
-- export_trails.py prints every digit: at most 0.056 m (decision 8's own
-- bound), which moves a place's measured distance by no more than that.
--
-- With no rows the distance check is skipped, which export_challenges.py
-- also does with no centerline, and says so: the test
-- challenges_distance_check_has_a_centerline_to_measure_against warns.
with lines as (
    select * from {{ ref('trail_lines', v=1) }}
    where line_kind not in ('network', 'club')
)

select
    trail_line_id,
    geom_geojson
from lines
where source_key = 'centerline'
