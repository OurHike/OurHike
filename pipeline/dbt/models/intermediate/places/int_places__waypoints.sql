-- The published waypoints a trailhead, parking or town row of places.json
-- comes from (PL05): every record export_places.py's load_point_places()
-- reads, which is poi_trailhead.geojson, poi_parking.geojson and
-- poi_resupply.geojson (export_poi.py) and then nearby_poi.geojson
-- (export_nearby_poi.py), here as the points_of_interest mart's rows those
-- four files are written from: `phone_files` poi_by_type or nearby_poi, never
-- retired_poi, and `poi_type` trailhead, parking or resupply.
--
-- Each column is what load_point_places() reads off the file:
-- - poi_id, poi_type, source, source_feature_id, name: the published
--   properties of those names (`poi_id` is the file's `id`);
-- - source_key: the registry key that source is (`parking` for
--   `atc_parking`, lib/source_registry.py's POI_SOURCE_KEYS, else the source
--   itself), which is the mart's `source_key`, and which source_entry() looks
--   up for the source's `place_kind` and organization;
-- - lon, lat: the `lon` and `lat` the file publishes, AS A PHONE PARSES
--   THEM, because places.json copies the value as read. For a
--   poi_<type>.geojson row that is GDAL's printing of the double property
--   (macros/gdal_geojson.sql's gdal_geojson_double(), the macro
--   macros/poi_feature_collection.sql writes those files with), not the
--   source's double: -74.29599999999999 is written -74.296 (measured
--   2026-10-02). A nearby_poi.geojson row publishes the double whole, as
--   json.dumps prints it and pub_nearby_poi writes it;
-- - waypoint_order: the row's place in load_point_places()'s list: the three
--   poi_<type>.geojson files in POINT_PLACE_KINDS order (trailhead, parking,
--   resupply), which load_destination_pois() reads them in, each in its
--   file's record order, then nearby_poi.geojson in its record order. The
--   first row wins a published id two rows carry; `poi_id` breaks a tie in
--   record order, which nearby_poi has where one source row publishes two
--   POIs, so the choice is deterministic;
-- - club, _loaded_at: the mart's.
--
-- A name or source_feature_id that GDAL's AUTODETECT_JSON_STRINGS would
-- write as JSON (text that starts with [ and ends with ], or { and }, and
-- parses) is read here as the text, where the Python would read the JSON
-- value back and print it with str(). Measured 2026-10-02 on the live ATC
-- Parking and Communities, OPRHP facilities and DEC parking layers (11,217
-- features, 119,352 string values): 481 values are bracketed, every one an
-- ATC Parking GlobalID such as `{03D8B54B-...}`, and none parses as JSON, so
-- no row reaches that case today.
with pois as (
    select * from {{ ref('points_of_interest', v=1) }}
    where
        phone_files in ('poi_by_type', 'nearby_poi')
        and poi_type in ('trailhead', 'parking', 'resupply')
),

-- POINT_PLACE_KINDS' order.
type_order (poi_type, file_rank) as (
    values
    ('trailhead', 0),
    ('parking', 1),
    ('resupply', 2)
)

select
    pois.poi_id,
    pois.poi_type,
    pois.source,
    pois.source_key,
    pois.source_feature_id,
    pois.name,
    case
        when pois.phone_files = 'poi_by_type'
            then {{ gdal_geojson_double('pois.lon') }}
        else pois.lon
    end as lon,
    case
        when pois.phone_files = 'poi_by_type'
            then {{ gdal_geojson_double('pois.lat') }}
        else pois.lat
    end as lat,
    row_number() over (
        order by
            pois.phone_files = 'nearby_poi' asc,
            case
                when pois.phone_files = 'poi_by_type' then type_order.file_rank
            end asc,
            pois.record_order asc,
            pois.poi_id asc
    ) - 1 as waypoint_order,
    pois.club,
    pois._loaded_at
from pois
inner join type_order on pois.poi_type = type_order.poi_type
