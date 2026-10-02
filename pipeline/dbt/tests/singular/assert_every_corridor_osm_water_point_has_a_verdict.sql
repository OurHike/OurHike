-- Every OSM water point in the corridor has a reachability verdict (PO08).
-- int_points_of_interest__reached drops a point with none, which is the safe
-- direction for one point; a build in which the verdicts and the points
-- disagree is a broken build, and export_poi.py's read_sources() refuses to
-- run in the same state ("osm_water.geojson is present but
-- osm_water_reach.json is not") rather than publish without the gate. So
-- the drop stays and this fails the build. step_osm_water_grade writes one
-- verdict per row of int_points_of_interest__osm_water_reach, so a row here
-- means the step ran on other points than the model holds. Fails by
-- returning a row.
select osm_id
from {{ ref('int_points_of_interest__osm_water_verdicts') }}
where not has_verdict
