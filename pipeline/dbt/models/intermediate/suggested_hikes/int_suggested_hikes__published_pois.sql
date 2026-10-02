-- INTERFACE: replace with poi's model
--
-- The POIs a highlight's legs resolve against (SH12): every POI
-- export_poi.py publishes in its eight poi_<type>.geojson files, with its
-- published `id` and `mile`, as export_highlights.py's load_published_pois()
-- and lib/highlights.py's poi_miles() read them. A POI that published with
-- no mile carries none, and that is a gap, not a zero: mile 0.0 is Springer
-- Mountain, a real place a highlight could start. The ids have to be the
-- ones already on the device and the miles the ones every other POI on it
-- carries, which is why this reads the published POIs and never ATC's raw
-- points. On wk/poi that is `points_of_interest` where
-- `phone_files = 'poi_by_type'`, its `poi_id` and `mile`.
--
-- Zero rows until the points_of_interest mart publishes those columns (the
-- poi family, stage 3 of #1793 — Rebuild the data platform as dlt → dbt:
-- seven contracted marts, a monthly refresh, published docs, and lighter
-- phone downloads), so every highlight is refused as having no published
-- mile, which is export_highlights.py's own answer when it finds no POI file.
-- It reads the mart only so that it is not a root model.
select
    cast(null as varchar) as poi_id,
    cast(null as double) as mile
from {{ ref('points_of_interest') }}
where false
