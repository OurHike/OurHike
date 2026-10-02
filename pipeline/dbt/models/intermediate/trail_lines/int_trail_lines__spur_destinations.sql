-- placeholder: the points_of_interest mart fills this
--
-- The published POIs a spur may lead to (TL28), as export_spurs.py's
-- load_destination_pois() reads them: export_poi.py's records of the five
-- DESTINATION_POI_TYPES (shelter, water, campsite, resupply, viewpoint),
-- resolved against what the phone holds, so a destination id is one the
-- client can find (PR #472 — Read the POI files by the name that writes
-- them). Privies, parking and trailheads are
-- NOT_A_DESTINATION_POI_TYPES, for the reasons export_spurs.py gives;
-- int_trail_lines__spurs keeps only the five types itself, so a row of
-- another type here is never a destination.
--
-- THE INTERFACE, one row per published POI of those types:
-- - poi_id: its published `id`;
-- - poi_type: its type;
-- - latitude, longitude: its published `lat` and `lon`;
-- - destination_order: its place in load_destination_pois()'s list, the
--   types in DESTINATION_POI_TYPES order and each type's file in its own
--   order. A tie between two POIs at one distance goes to the first, as
--   lib/spurs.PointIndex.nearest's strict `<` keeps it.
--
-- No rows until the points_of_interest mart publishes those columns (the
-- poi family, stage 3 of #1793 — Rebuild the data platform as dlt → dbt:
-- seven contracted marts, a monthly refresh, published docs, and lighter
-- phone downloads), so every spur's destination is null here,
-- which is export_spurs.py's own answer when it finds no POI file. It reads
-- the mart only so that it is not a root model.
select
    cast(null as varchar) as poi_id,
    cast(null as varchar) as poi_type,
    cast(null as double) as latitude,
    cast(null as double) as longitude,
    cast(null as bigint) as destination_order
from {{ ref('points_of_interest') }}
where false
