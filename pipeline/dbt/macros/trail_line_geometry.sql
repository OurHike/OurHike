{#-
    Three things export_trails.py does to a published line, in SQL, for the
    trail_lines family's models.

    line_vertices(line): one LineString's vertices as [x, y] pairs, in order,
    a repeated vertex kept (ST_Points keeps repeats, measured 2026-10-02 on
    dbt 2.0.6's DuckDB: MULTILINESTRING ((1 2, 1 2, 3 4.5), ...) gave five
    points). shapely.get_coordinates gives the same list.

    line_is_drawable(geom): export_trails._has_drawable_geometry. A line puts
    pixels on a map only when every part has two DISTINCT vertices, because
    Douglas-Peucker on a line shorter than its tolerance can leave two
    identical points, which render as nothing (that function's docstring
    says where it measured five). ALL parts, so a MultiLineString with one
    collapsed part is not drawable, and nothing empty is.

    simplified_in_metres(geom, tolerance): simplify_records()' pass on one
    line: taken to EPSG:5070, where a metre is a metre on both axes,
    Douglas-Peucker'd at `tolerance` metres (ST_Simplify and
    shapely.simplify(..., preserve_topology=False) are both GEOS's), and taken
    back, always_xy on both legs. Its two refusals are simplify_records' own:
    a tolerance of 0 returns the line untouched, "the supported way for a
    consumer that needs full precision to ask for it", where the round trip
    through EPSG:5070 alone moves a vertex (945 of 1,000 points near 41 N, by
    up to 8.5e-14 degrees, measured 2026-10-02 on DuckDB 1.5.5), and a
    negative one stops the build, as its ValueError stops the export. The
    caller keeps the line it was given where the result is not drawable.
-#}
{% macro line_vertices(line) -%}
list_transform(
    st_dump(st_points({{ line }})),
    lambda vertex: [
        st_x(struct_extract(vertex, 'geom')),
        st_y(struct_extract(vertex, 'geom'))
    ]
)
{%- endmacro %}

{% macro line_is_drawable(geom) -%}
coalesce(
    not st_isempty({{ geom }})
    and list_bool_and(
        list_transform(
            st_dump({{ geom }}),
            lambda part: len(
                list_distinct({{ line_vertices("struct_extract(part, 'geom')") }})
            ) >= 2
        )
    ),
    false
)
{%- endmacro %}

{% macro simplified_in_metres(geom, tolerance) -%}
case
    when cast({{ tolerance }} as double) < 0
        then error(
            'simplified_in_metres: the tolerance must be >= 0, got '
            || cast({{ tolerance }} as varchar)
        )
    when cast({{ tolerance }} as double) = 0 then {{ geom }}
    else st_transform(
        st_simplify(
            st_transform({{ geom }}, 'EPSG:4326', 'EPSG:5070', always_xy := true),
            {{ tolerance }}
        ),
        'EPSG:5070',
        'EPSG:4326',
        always_xy := true
    )
end
{%- endmacro %}
