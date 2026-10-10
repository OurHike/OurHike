-- Decision 76: the phone counts a route vertex as in a state only when it is
-- more than `edge_margin_m` inside the state's simplified shape
-- (int_closures__notice_state_shapes says why that is safe only while the
-- simplified edge stays within the margin of the state's own). This measures
-- it on every build: the distance from each of the original TIGER edge's
-- vertices to the simplified edge, in the state's own frame, whose metres
-- overstate the ground's. Measured 2026-10-04 on the 14 states the seed then
-- named: worst 341 m, Colorado, against a 500 m margin. Returns one row per
-- state whose worst vertex is past the margin; the answer to a failure is a
-- smaller tolerance, never a wider margin nobody measured.
with shapes as (
    select
        shapes.state,
        shapes.frame,
        shapes.edge_margin_m,
        states.geom,
        st_boundary(
            st_transform(
                st_geomfromgeojson(cast(shapes.phone_geometry as varchar)),
                'EPSG:4269',
                shapes.frame,
                always_xy := true
            )
        ) as phone_edge
    from {{ ref('int_closures__notice_state_shapes') }} as shapes
    inner join {{ ref('stg_census__states') }} as states
        on shapes.state = states.state
),

vertices as (
    select
        shapes.state,
        shapes.frame,
        shapes.edge_margin_m,
        shapes.phone_edge,
        unnest(st_dump(st_points(st_boundary(shapes.geom)))).geom as vertex
    from shapes
),

offsets as (
    select
        state,
        edge_margin_m,
        st_distance(
            st_transform(vertex, 'EPSG:4269', frame, always_xy := true),
            phone_edge
        ) as offset_m
    from vertices
)

select
    state,
    max(offset_m) as worst_offset_m,
    any_value(edge_margin_m) as edge_margin_m
from offsets
group by state
having max(offset_m) > any_value(edge_margin_m)
