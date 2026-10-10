{#-
    One poi_<type>.geojson document from the points_of_interest mart, for the
    eight pub_poi_<type> writers: today's shape (decision 44 makes it v1), as
    export_poi.py's write_poi_type() has GDAL's GeoJSON driver write it. A
    FeatureCollection named for the type; each feature carries every one of
    POI_COLUMNS in their order, null where a POI has none, and its point.

    Each value is the one a phone parses out of GDAL's text
    (macros/gdal_geojson.sql): a DOUBLE property as GDAL prints a double, an
    integer as an integer, a string as GDAL's AUTODETECT_JSON_STRINGS writes
    it (the `nearby` and `photos` JSON become JSON, as in the Python's file),
    and the point is the mart's geom_geojson, already at GDAL's coordinate
    precision. Features in export_poi.py's record order. `features` is
    coalesced to [] because an empty type writes an empty collection, never
    null: trailhead publishes none (ALLOWED_EMPTY_POI_TYPES).

    `relation` is the writer's own CTE over ref('points_of_interest'), so the
    ref stays in the model where dbt sees it.

    `version` is the mart version the relation reads (decision 44). At 1,
    the default, the document is today's shape, above. At 2 (stage 6 of
    #1793, the eight pub_poi_<type>_v2 writers) the `lat` and `lon`
    properties are left out, because the v2 mart holds a POI's position once,
    as geom_geojson at 6 decimals (points_of_interest_v2.sql), and every other
    property is v1's, in v1's order. So there is one list of properties for
    both shapes, and a property added here reaches both.
-#}
{% macro poi_by_type_feature_collection(relation, poi_type, version=1) -%}
select
    'FeatureCollection' as type,
    '{{ poi_type }}' as name,
    coalesce(
        list(
            json_object(
                'type', 'Feature',
                'properties', json_object(
                    'id', {{ gdal_geojson_string('poi_id') }},
                    'poi_type', {{ gdal_geojson_string('poi_type') }},
                    'trail_id', {{ gdal_geojson_string('trail_id') }},
                    'source', {{ gdal_geojson_string('source') }},
                    'source_feature_id',
                    {{ gdal_geojson_string('source_feature_id') }},
                    'name', {{ gdal_geojson_string('name') }},
                    {%- if version == 1 %}
                    'lat', {{ gdal_geojson_double('lat') }},
                    'lon', {{ gdal_geojson_double('lon') }},
                    {%- endif %}
                    'mile', {{ gdal_geojson_double('mile') }},
                    'confidence', {{ gdal_geojson_string('confidence') }},
                    'capacity', capacity,
                    'water_distance_ft', water_distance_ft,
                    'water_distance_source',
                    {{ gdal_geojson_string('water_distance_source') }},
                    'description', {{ gdal_geojson_string('description') }},
                    'nearby', nearby,
                    'photo_key', {{ gdal_geojson_string('photo_key') }},
                    'photo_page_url', {{ gdal_geojson_string('photo_page_url') }},
                    'photo_author', {{ gdal_geojson_string('photo_author') }},
                    'photo_license', {{ gdal_geojson_string('photo_license') }},
                    'photo_taken', {{ gdal_geojson_string('photo_taken') }},
                    'photos', photos,
                    'site_id', {{ gdal_geojson_string('site_id') }},
                    'site_role', {{ gdal_geojson_string('site_role') }},
                    'site_name', {{ gdal_geojson_string('site_name') }}
                ),
                'geometry', cast(geom_geojson as json)
            )
            order by record_order
        ),
        []
    ) as features
from {{ relation }}
where poi_type = '{{ poi_type }}'
{%- endmacro %}
