-- The POIs a highlight's legs resolve against (SH12): every POI
-- export_poi.py publishes in its eight poi_<type>.geojson files, with its
-- published `id` and `mile`, as export_highlights.py's load_published_pois()
-- and lib/highlights.py's poi_miles() read them: the points_of_interest
-- mart's `poi_by_type` rows, which pub_poi_<type> writes those eight files
-- from. A POI that published with no mile carries none, and that is a gap,
-- not a zero: mile 0.0 is Springer Mountain, a real place a highlight could
-- start. The ids have to be the ones already on the device and the miles the
-- ones every other POI on it carries, which is why this reads the published
-- POIs and never ATC's raw points.
select
    poi_id,
    mile
from {{ ref('points_of_interest', v=1) }}
where phone_files = 'poi_by_type'
