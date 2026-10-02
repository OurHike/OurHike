{#-
    Two questions export_trails.py asks of a published line, in SQL, for the
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
