{#-
    notice_phone_geometry(geom): a club notice's own geometry as
    conditions/notices.json carries it (pub_conditions_notices, whose header
    has the measurements; decision 77, the maintainer's poll of 2026-10-05).
    `geom` is a valid geometry in EPSG:4326. The result is in EPSG:4326 at 5
    decimal places, and may be empty, which the writer answers by keeping the
    full shape. A macro so that
    tests/singular/assert_a_notice_area_covers_every_vertex_of_its_source.sql
    holds the writer's own SQL to its one promise, not a copy of it.

    AN AREA (dimension 2) is simplified at 10 m, as it was before decision
    77, grown outward by `notice_area_m`, and simplified with the topology
    preserved at `notice_area_m`. Where that shape holds the source's own area
    at least `notice_area_snap_allowance_m` inside its edge, it is published as
    it is; elsewhere it is joined to the source's area grown by that
    allowance. Either way it covers every point of the source's area, the
    vertices among them, after the 5 decimal places too (Reasoned below; held
    by the singular test above, and measured on UA's live file in the
    writer's header).

    Why the join, when growing by the tolerance looks enough: GEOS's
    topology-preserving simplifier cuts further than its tolerance, which
    int_closures__notice_state_shapes also found (a 341 m offset at 250 m).
    Measured 2026-10-05 on UA's live notices.json, grown 100 m and simplified
    at 100 m without the join: 256 of 765,166 area vertices, in 101 of 1,063
    areas, ended up outside the published area, the worst 61 m outside. With
    it, 252 of the 1,063 areas take the join, and the file is 10,832,088
    bytes, against 10,782,727 grown and simplified the same way with no join
    and no 10 m step.

    Why the 10 m step first: the growth and the second simplification take
    longer the more vertices they are given, and the source's own outline is
    a survey's, while the join reads that outline whole, so the step costs
    the cover nothing (Reasoned). Why list_transform's lambda: it binds the
    simplified shape once for the check and the join; written out three times
    in a CASE, DuckDB computed it each time (measured 2026-10-05, about 1.6
    times as long). @unvalidated: what this costs the hourly build. On the
    live file's geometries, in a shared sandbox (load average 12 to 18), the
    shaping before decision 77 took 7.4 s and this 36 to 39 s (measured
    2026-10-05), and publish-conditions.yml's build step, capped at 4
    minutes, already took 162 to 171 s on soak runs 532 to 536
    (pipeline/ELT.md). Nobody has measured it on a runner against the
    sources' full outlines; the first UA run after this lands says.

    Why 1 m covers the 5 decimal places: rounding to a 0.00001-degree grid
    moves each point of an edge by at most half a cell's diagonal, and in this
    frame a degree is at most 111,319.49 m east-west and 110,574.27 m
    north-south, so at most 0.5 x 0.00001 x 156,902 = 0.78 m (Reasoned).
    Joined or not, every edge of the shape is at least 0.99 m from the
    source's area (the check's and the join's 1 m offsets draw their arcs as
    chords, 5 mm short), so none can cross it.

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
    {%- set allowance = var('notice_area_snap_allowance_m') -%}
    case
        when st_dimension({{ geom }}) = 2
            then st_reduceprecision(
                st_affine(
                    list_transform(
                        [
                            st_simplifypreservetopology(
                                st_buffer(
                                    st_simplifypreservetopology({{ framed }}, 10),
                                    {{ var('notice_area_m') }}
                                ),
                                {{ var('notice_area_m') }}
                            )
                        ],
                        lambda simplified: case
                            when st_covers(
                                st_buffer(simplified, -{{ allowance }}), {{ framed }}
                            )
                                then simplified
                            else st_union(
                                simplified, st_buffer({{ framed }}, {{ allowance }})
                            )
                        end
                    )[1],
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
