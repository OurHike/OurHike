{{ config(materialized='table') }}
-- The centerline's chains with the A.T. mile of every vertex (TL22),
-- export_trails.vertex_miles(): what trail_miles.json publishes beside
-- trails.geojson, so a phone reads the same mile a POI carries instead of
-- measuring the line itself (#1192 — A returning hiker's launch freezes
-- for ten seconds while every waypoint is placed on the trail, on the main
-- thread).
--
-- Each vertex is projected onto int_trail_lines__mile_axis by the axis_mile
-- macro, the axis's one recipe, as export_poi.attach_miles projects a
-- shelter: the vertex in EPSG:5070, its nearest calibrated piece (the
-- macro's header has the tie order, and the one junction where it mattered),
-- the distance along that piece, and the piece's mile there. The mile is
-- rounded to trail_lines_mile_decimals (3) half to even, as numpy's np.round
-- does (multiply, rint, divide), which is not Python's round().
--
-- Measured 2026-10-02 on ATC's live centerline: all 216,767 vertex miles of
-- its 463 chains equal export_trails.py's trail_miles.json to the bit, with
-- the same 112 backward steps.
--
-- monotonic_breaks counts the steps that run against the chain's own
-- direction, export_trails._monotonic_breaks: forwards when the last mile is
-- at least the first. Counted rather than smoothed, because the client
-- splits a piece at each one (client/src/lib/trailPosition.ts).
--
-- Carried as JSON text, `vertex_miles_json`, because a dbt 2.0.6 unit test
-- cannot hold a list, and compares a double only to one decimal place.
with chains as (
    select * from {{ ref('int_trail_lines__at_chains') }}
),

vertices as (
    select
        trail_line_id,
        vertex_index,
        st_transform(
            st_point(list_extract(xy, 1), list_extract(xy, 2)),
            'EPSG:4326',
            'EPSG:5070',
            always_xy := true
        ) as vertex_point
    from (
        select
            trail_line_id,
            unnest({{ line_vertices('geom') }}) as xy,
            generate_subscripts({{ line_vertices('geom') }}, 1) as vertex_index
        from (
            select
                trail_line_id,
                st_geomfromtext(geom_wkt) as geom
            from chains
        ) as parsed
    )
),

located as {{
    axis_mile('vertices', ['trail_line_id', 'vertex_index'], 'vertex_point')
}},

miles as (
    select
        trail_line_id,
        vertex_index,
        round_even(mile * pow(10, {{ var('trail_lines_mile_decimals') }}), 0)
        / pow(10, {{ var('trail_lines_mile_decimals') }}) as mile
    from located
),

per_chain as (
    select
        trail_line_id,
        list(mile order by vertex_index) as vertex_miles
    from miles
    group by trail_line_id
),

breaks as (
    select
        trail_line_id,
        vertex_miles,
        cast(
            len(
                list_filter(
                    list_transform(
                        range(1, len(vertex_miles)),
                        lambda step: case
                            when
                                list_extract(vertex_miles, -1)
                                >= list_extract(vertex_miles, 1)
                                then
                                    list_extract(vertex_miles, step + 1)
                                    - list_extract(vertex_miles, step)
                            else
                                list_extract(vertex_miles, step)
                                - list_extract(vertex_miles, step + 1)
                        end
                    ),
                    lambda difference: difference < 0
                )
            ) as integer
        ) as monotonic_breaks
    from per_chain
)

-- A left join, so a chain the axis gave no mile keeps its line and fails
-- the not_null test on vertex_miles_json, rather than leaving trails.geojson
-- without it.
select
    chains.*,
    cast(to_json(breaks.vertex_miles) as varchar) as vertex_miles_json,
    breaks.monotonic_breaks
from chains
left join breaks on chains.trail_line_id = breaks.trail_line_id
