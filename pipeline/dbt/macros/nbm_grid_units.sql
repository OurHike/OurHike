{#-
    A lon/lat polygon in NOAA's NBM grid units, as lib/nbm_grid.py's
    overlapping() transforms an NWS alert's polygon before it tests the
    squares (#1793, stage 3, WN03): each vertex projected onto the grid's
    Lambert conformal plane (var nbm_grid_proj4, on GRIB's sphere), then
    col = (x - origin_x) / square_m and row = (origin_y - y) / square_m, so
    square (row, col) is the box from (col, row) to (col + 1, row + 1).

    THE DIVISION IS PYTHON'S, VERTEX BY VERTEX. ST_Affine and ST_TransScale
    multiply by the reciprocal, which can land a vertex one unit in the last
    place away from numpy's quotient, and whether a polygon only touches a
    square's edge turns on exactly that. So the projected polygon is read as
    GeoJSON (which DuckDB prints at the shortest length that reads back to
    the same double), each coordinate pair divided as the Python divides it,
    and the polygon rebuilt. Measured 2026-10-02 on DuckDB 1.5.5 against
    lib/nbm_grid.py's _to_grid_units: every vertex of a polygon, a
    multipolygon, and tests/test_export_weather_alerts.py's Pinkham Notch
    shape identical, bit for bit; and ST_Transform with this PROJ string
    agreed with pyproj's to the last bit at the four points
    tests/test_lib_nbm_grid.py pins to GDAL.

    Polygons and multipolygons, which is what NWS draws. Any other type is
    null here, so int_warnings__nws_placed places that alert by nothing at
    all rather than by a guess; shapely would place it.
-#}
{% macro nbm_grid_units(geom) -%}
    {%- set ox = var('nbm_grid_origin_x') -%}
    {%- set oy = var('nbm_grid_origin_y') -%}
    {%- set s = var('nbm_grid_square_m') -%}
    {%- set lcc -%}
        st_transform({{ geom }}, 'EPSG:4326', '{{ var("nbm_grid_proj4") }}', always_xy := true)
    {%- endset -%}
    case st_geometrytype({{ geom }})
        when 'POLYGON'
            then st_geomfromgeojson(json_object(
                'type', 'Polygon',
                'coordinates', list_transform(
                    cast(json_extract(st_asgeojson({{ lcc }}), '$.coordinates') as double[][][]),
                    lambda ring: list_transform(
                        ring,
                        lambda p: [(p[1] - ({{ ox }})) / {{ s }}, ({{ oy }} - p[2]) / {{ s }}]
                    )
                )
            ))
        when 'MULTIPOLYGON'
            then st_geomfromgeojson(json_object(
                'type', 'MultiPolygon',
                'coordinates', list_transform(
                    cast(json_extract(st_asgeojson({{ lcc }}), '$.coordinates') as double[][][][]),
                    lambda poly: list_transform(
                        poly,
                        lambda ring: list_transform(
                            ring,
                            lambda p: [(p[1] - ({{ ox }})) / {{ s }}, ({{ oy }} - p[2]) / {{ s }}]
                        )
                    )
                )
            ))
    end
{%- endmacro %}
