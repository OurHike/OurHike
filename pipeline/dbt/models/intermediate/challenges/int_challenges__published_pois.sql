-- The published POIs a challenge place may name (CH01, CH02, CH03), as
-- export_challenges.load_published_pois() reads them: the properties of
-- every feature in export_poi.py's eight poi_<type>.geojson files, which are
-- the points_of_interest mart's `poi_by_type` rows, and of no other file.
-- Not nearby_poi.geojson and not retired_poi.geojson: an item names an id
-- already on the device, and a place's mile is the A.T. mile every other
-- screen shows. A feature with no truthy `id` is skipped there; the mart's
-- poi_id is never null, and an empty one is skipped here too.
--
-- `mile`, `lat` and `lon` are the values json.loads reads out of those
-- files, which is not always the double the mart holds: GDAL's GeoJSON
-- writer prints a DOUBLE property its own way, and gdal_geojson_double() is
-- that printing (macros/gdal_geojson.sql, measured on 182,408 doubles: 60,301
-- read back as another double, -73.99000000000001 as -73.99). The pub_poi_
-- writers print them through the same macro, so a place publishes the
-- coordinate its pin is drawn at.
--
-- A string property that starts with [ and ends with ], or { and }, and
-- parses as JSON, GDAL writes as that JSON (gdal_geojson_string()); here
-- `trail_id`, `poi_type` and `name` stay text. Reasoned to matter nowhere:
-- no POI type or trail id has that shape, and a name of that shape would
-- publish here as the name's text where today's file publishes the JSON.
with pois as (
    select * from {{ ref('points_of_interest') }}
    where phone_files = 'poi_by_type'
)

select
    poi_id,
    trail_id,
    poi_type,
    name,
    {{ gdal_geojson_double('mile') }} as mile,
    {{ gdal_geojson_double('lat') }} as lat,
    {{ gdal_geojson_double('lon') }} as lon
from pois
where poi_id != ''
