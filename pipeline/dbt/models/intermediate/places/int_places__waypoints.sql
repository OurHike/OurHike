-- INTERFACE: replace with poi's model
--
-- The published waypoints a trailhead, parking or town row of places.json
-- comes from (PL05): every record export_places.py's load_point_places()
-- reads, which is poi_trailhead.geojson, poi_parking.geojson and
-- poi_resupply.geojson (export_poi.py) and then nearby_poi.geojson
-- (export_nearby_poi.py). poi builds the points_of_interest mart those files
-- are written from on branch wk/poi; at integration this model selects those
-- rows from the mart and stops being an interface.
--
-- THE INTERFACE, one row per published POI of type trailhead, parking or
-- resupply, in a file a phone reads (the mart's `phone_files` poi_by_type or
-- nearby_poi, never retired_poi):
-- - poi_id: its published `id`;
-- - poi_type: trailhead, parking or resupply;
-- - source: its published `source`, the id namespace (`atc_parking`,
--   `oprhp_facilities`);
-- - source_key: the registry key that source is (`parking` for
--   `atc_parking`, lib/source_registry.py's POI_SOURCE_KEYS, else the source
--   itself), which is the mart's `source_key`;
-- - source_feature_id: its published `source_feature_id`, which a town's
--   state is looked up by;
-- - name: its published `name`, null where it has none;
-- - lon, lat: the `lon` and `lat` the file publishes, AS A PHONE PARSES
--   THEM. For a poi_<type>.geojson row that is GDAL's printing of the
--   double property, not the source's double: -74.29599999999999 is written
--   -74.296 (measured 2026-10-02, and wk/poi's gdal_geojson_double() macro
--   is that printing in SQL). For a nearby_poi.geojson row it is the double,
--   which json.dumps writes whole. places.json copies the value as read;
-- - waypoint_order: the row's place in load_point_places()'s list, the three
--   poi_<type>.geojson files in POINT_PLACE_KINDS order (trailhead, parking,
--   resupply), each file in its own order, then nearby_poi.geojson in its
--   order. The first row wins a published id two rows carry;
-- - club, _loaded_at: the mart's.
--
-- No rows until then, so places.json holds no trailhead, parking or town
-- here, which is export_places.py's own answer when no POI file is on disk.
-- It reads the points_of_interest mart only so that it is not a root model.
select
    cast(null as varchar) as poi_id,
    cast(null as varchar) as poi_type,
    cast(null as varchar) as source,
    cast(null as varchar) as source_key,
    cast(null as varchar) as source_feature_id,
    cast(null as varchar) as name,
    cast(null as double) as lon,
    cast(null as double) as lat,
    cast(null as bigint) as waypoint_order,
    cast(null as varchar) as club,
    cast(null as timestamptz) as _loaded_at
from {{ ref('points_of_interest') }}
where false
