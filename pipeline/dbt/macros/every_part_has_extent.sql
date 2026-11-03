{#- True where a geometry is not empty and every part of it spans some
    width or height, so a phone can draw it; false otherwise, never null.
    A part simplified down to one point (its x and y extents both zero) is
    what this refuses: the trail-line writers leave such a line out rather
    than publish a line a map cannot draw.

    Example: {{ every_part_has_extent('reduced') }} as drawable -#}
{% macro every_part_has_extent(geom) -%}
    coalesce(
        not st_isempty({{ geom }})
        and list_bool_and(
            list_transform(
                st_dump({{ geom }}),
                lambda part: (
                    st_xmin(struct_extract(part, 'geom'))
                    < st_xmax(struct_extract(part, 'geom'))
                )
                or (
                    st_ymin(struct_extract(part, 'geom'))
                    < st_ymax(struct_extract(part, 'geom'))
                )
            )
        ),
        false
    )
{%- endmacro %}
