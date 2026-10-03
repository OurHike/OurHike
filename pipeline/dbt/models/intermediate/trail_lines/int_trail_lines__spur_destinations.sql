{{ config(materialized='table') }}
{%- set destination_types = var('trail_lines_spur_destination_poi_types') %}
-- The published POIs a spur may lead to (TL28), as export_spurs.py's
-- load_destination_pois() reads them: the points_of_interest mart's rows in
-- the eight poi_<type>.geojson files (`phone_files` 'poi_by_type'), of the
-- five DESTINATION_POI_TYPES (trail_lines_spur_destination_poi_types:
-- shelter, water, campsite, resupply, viewpoint), so a destination id is one
-- the client can find (PR #472 — Read the POI files by the name that writes
-- them). Privies, parking and trailheads are NOT_A_DESTINATION_POI_TYPES,
-- for the reasons export_spurs.py gives; int_trail_lines__spurs filters on
-- the same var.
--
-- `latitude` and `longitude` are the `lat` and `lon` properties as the file
-- prints them (macros/gdal_geojson.sql's gdal_geojson_double), which is
-- what load_destination_pois() parses and lib/spurs.py measures from. GDAL's
-- text read back as a different double for 60,301 of the 182,408 values that
-- macro was measured on, so the source's own lat can be an ulp or three off
-- the one the Python measures with.
--
-- `destination_order` is the POI's place in load_destination_pois()'s list:
-- the types in DESTINATION_POI_TYPES order, then each file's own order (the
-- mart's record_order). A tie between two POIs at one distance goes to the
-- first, as lib/spurs.PointIndex.nearest's strict `<` keeps it.
with pois as (
    select * from {{ ref('points_of_interest') }}
    where phone_files = 'poi_by_type'
)

select
    poi_id,
    poi_type,
    {{ gdal_geojson_double('lat') }} as latitude,
    {{ gdal_geojson_double('lon') }} as longitude,
    row_number() over (
        order by
            list_position(
                [
                    {%- for poi_type in destination_types %}
                    '{{ poi_type }}'{{ ',' if not loop.last }}
                    {%- endfor %}
                ],
                poi_type
            ),
            record_order
    ) - 1 as destination_order
from pois
where poi_type in (
    {%- for poi_type in destination_types %}
    '{{ poi_type }}'{{ ',' if not loop.last }}
    {%- endfor %}
)
