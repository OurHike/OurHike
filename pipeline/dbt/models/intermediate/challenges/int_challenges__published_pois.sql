-- INTERFACE: replace with the poi family's points_of_interest mart (wk/poi)
--
-- The published POIs a challenge place may name (CH01, CH02, CH03), as
-- export_challenges.load_published_pois() reads them: the properties of
-- every feature in export_poi.py's eight per-type files, data/processed/poi/
-- <type>.geojson, and of no other file. Not nearby_poi.geojson and not
-- retired_poi.geojson: an item names an id already on the device, and a
-- place's mile is the A.T. mile every other screen shows.
--
-- THE INTERFACE, one row per POI in those files:
-- - poi_id: its published `id`;
-- - trail_id, poi_type: its `trail_id` and `poi_type` properties;
-- - name: its `name` property;
-- - mile, lat, lon: its `mile`, `lat` and `lon` properties AS THE FILE PRINTS
--   THEM, which is what json.loads reads. GDAL's GeoJSON writer prints a
--   DOUBLE property with gdal_geojson_double() (wk/poi's macro, measured on
--   182,408 doubles: 60,301 read back as another double, -73.99000000000001
--   as -73.99), so the mart's own `lat` and `lon` go through it; `mile` is
--   already cut to 3 places, which that printing returns unchanged.
--
-- At integration, with wk/poi's mart and macros in the build, this body is
-- (Jinja braces left out here, because a comment is rendered too):
--
--     select
--         poi_id,
--         trail_id,
--         poi_type,
--         name,
--         <gdal_geojson_double('mile')> as mile,
--         <gdal_geojson_double('lat')> as lat,
--         <gdal_geojson_double('lon')> as lon
--     from <ref('points_of_interest')>
--     where phone_files = 'poi_by_type'
--
-- with each <...> written as a Jinja expression, cast to double if the macro
-- returns text. Until then it has no rows, so every place drops as "not in the
-- published POIs" and every trail as "carried by no published POI", which is
-- export_challenges.py's own answer when it finds no POI file. It reads the
-- stage-1 mart only so that it is not a root model.
select
    cast(null as varchar) as poi_id,
    cast(null as varchar) as trail_id,
    cast(null as varchar) as poi_type,
    cast(null as varchar) as name,
    cast(null as double) as mile,
    cast(null as double) as lat,
    cast(null as double) as lon
from {{ ref('points_of_interest') }}
where false
