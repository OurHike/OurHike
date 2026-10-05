{#-
    notice_phone_geometry(geom): a club notice's own geometry as
    conditions/notices.json carries it (pub_conditions_notices, whose header
    has the measurements; decision 77, the maintainer's poll of 2026-10-05).
    `geom` is a valid geometry in EPSG:4326. The result is in EPSG:4326 at 5
    decimal places, and may be empty, which the writer answers by keeping the
    full shape. A macro so that
    tests/singular/assert_a_notice_area_covers_every_vertex_of_its_source.sql
    holds the writer's own SQL to its one promise, not a copy of it.

    AN AREA (dimension 2) is grown outward by `notice_area_m`, simplified with
    the topology preserved at `notice_area_m`, and then joined to itself grown
    by `notice_area_snap_allowance_m`, so it covers every point of the source's
    area, the vertices among them, after the 5 decimal places too (Reasoned
    below; held by the singular test above, and measured on UA's live file in
    the writer's header).

    Why the join, when growing by the tolerance looks enough: GEOS's
    topology-preserving simplifier cuts further than its tolerance, which
    int_closures__notice_state_shapes also found (a 341 m offset at 250 m).
    Measured 2026-10-05 on UA's live notices.json, grown 100 m and simplified
    at 100 m without the join: 256 of 765,166 area vertices, in 101 of 1,063
    areas, ended up outside the published area, the worst 61 m outside. Where
    the simplified edge stays out, the joined shape is the simplified one;
    where it cut in, the join puts back the source's own outline 1 m out,
    which costs 47,738 bytes on that file (10,830,465 with it, 10,782,727
    without).

    Why 1 m covers the 5 decimal places: rounding to a 0.00001-degree grid
    moves each point of an edge by at most half a cell's diagonal, and in this
    frame a degree is at most 111,319.49 m east-west and 110,574.27 m
    north-south, so at most 0.5 x 0.00001 x 156,902 = 0.78 m (Reasoned). Every
    edge of the joined shape is at least 0.99 m from the source's area (a
    grown outline's arcs are drawn as chords, 5 mm short at 1 m), so none can
    cross it.

    THE FRAME is an affine one, longitude and latitude scaled to metres, so a
    straight edge in it is a straight edge in longitude and latitude, which is
    how the phone reads one (lib/noticeGeometry.ts casts its rays on lon/lat as
    a plane) and how int_closures__notice_state_shapes simplifies. An edge
    straight in EPSG:5070 is a curve on the phone: the live file's longest area
    edge is 630 km, and its lon/lat chord sits 6.7 km off the EPSG:5070 line
    (measured 2026-10-05). The scales are the least a degree measures on
    WGS84 over the geometry: east-west at its latitude farthest from the
    equator (111,319.49 m x cos), north-south at the equator (110,574.27 m),
    so a frame metre is never more than a metre on the ground and the area
    grows by at least `notice_area_m` everywhere (Reasoned). The cosine is held
    at 0.01 or more, as the phone holds its own, so a shape at a pole cannot
    divide by zero.

    A LINE OR A POINT is not grown: Douglas-Peucker at 10 m with the topology
    preserved, in EPSG:5070 as before decision 77, then 5 decimal places.
-#}
{% macro notice_phone_geometry(geom) -%}
    {%- set kx -%}
        (111319.49 * greatest(cos(radians(greatest(abs(st_ymin({{ geom }})), abs(st_ymax({{ geom }}))))), 0.01))
    {%- endset -%}
    {%- set ky = '110574.27' -%}
    {%- set framed = 'st_affine(' ~ geom ~ ', ' ~ kx ~ ', 0, 0, ' ~ ky ~ ', 0, 0)' -%}
    case
        when st_dimension({{ geom }}) = 2
            then st_reduceprecision(
                st_affine(
                    st_union(
                        st_simplifypreservetopology(
                            st_buffer({{ framed }}, {{ var('notice_area_m') }}),
                            {{ var('notice_area_m') }}
                        ),
                        st_buffer(
                            {{ framed }},
                            {{ var('notice_area_snap_allowance_m') }}
                        )
                    ),
                    1 / {{ kx }}, 0, 0, 1 / {{ ky }}, 0, 0
                ),
                0.00001
            )
        else st_reduceprecision(
            st_transform(
                st_simplifypreservetopology(
                    st_transform(
                        {{ geom }}, 'EPSG:4326', 'EPSG:5070', always_xy := true
                    ),
                    10
                ),
                'EPSG:5070',
                'EPSG:4326',
                always_xy := true
            ),
            0.00001
        )
    end
{%- endmacro %}
