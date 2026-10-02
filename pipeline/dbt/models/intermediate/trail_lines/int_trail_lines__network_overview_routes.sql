{{ config(materialized='table') }}
-- The first half of network_overview.geojson's sketch, write_overview()'s
-- steps before the floor: every network line that ships, simplified again
-- to OVERVIEW_SIMPLIFY_TOLERANCE_M, and whether it is on a through route
-- (#1307, #1776; TL12, TL21).
--
-- THE COARSE LINE: simplify_records() at 100 m, in EPSG:5070, on the 1 m
-- line at full precision (int_trail_lines__network_navigation's, as
-- main() hands write_overview() the simplified records), keeping the 1 m
-- line where the pass would leave a part undrawable. The same pass as the
-- navigation model's, measured there against shapely at 100 m too.
--
-- A THROUGH ROUTE is a run of shared tread inside one trail identity whose
-- coarse lines total NAMED_TRAIL_THRESHOLD_MILES, 50, or more:
-- _through_routes(). The identity is (source, the trail's own name), the
-- name a published spelling int_trail_lines__network_name_aliases maps to a
-- long trail where it does, else the line's own; a line with no name, or a
-- blank one, has none. Two organizations' trails are never summed together
-- (the source stays in the identity), and two runs of one name that never
-- touch are two trails. The 50 is @unvalidated in its own comment
-- (export_nearby_trails.py's NAMED_TRAIL_THRESHOLD_MILES), which says what
-- would settle it.
--
-- RUNS OF TREAD, _chain_labels(): every vertex of a coarse line snapped to
-- a CHAIN_TOLERANCE_M, 200 m, grid in EPSG:5070, by Python's float floor
-- division (written out below, because floor(x / 200) can differ from it at
-- a cell edge), and two lines of one identity joined where any vertex of
-- each falls in one cell. The Python's union-find becomes a walk: each line
-- carries the smallest id that reaches it, passed only to lines whose id is
-- larger, so the walk floods each run from its smallest id and a run's label
-- is that id. The sum of a run's miles is a floating-point sum in another
-- order than the Python's; the two can differ only where a run sits within
-- an ulp of 50 miles.
with recursive navigation as (
    select * from {{ ref('int_trail_lines__network_navigation') }}
),

aliases as (
    select * from {{ ref('int_trail_lines__network_name_aliases') }}
),

reduced as (
    select
        *,
        st_geomfromtext(geom_wkt) as navigation_line,
        st_transform(
            st_simplify(
                st_transform(
                    st_geomfromtext(geom_wkt),
                    'EPSG:4326',
                    'EPSG:5070',
                    always_xy := true
                ),
                {{ var('trail_lines_network_overview_simplify_tolerance_m') }}
            ),
            'EPSG:5070',
            'EPSG:4326',
            always_xy := true
        ) as reduced
    from navigation
),

coarse as (
    select
        trail_line_id,
        source_key,
        name,
        blaze_color,
        trail_status,
        case
            when
                coalesce(
                    not st_isempty(reduced)
                    and list_bool_and(
                        list_transform(
                            st_dump(reduced),
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
                then reduced
            else navigation_line
        end as coarse_line
    from reduced
),

measured as (
    select
        *,
        st_transform(
            coarse_line, 'EPSG:4326', 'EPSG:5070', always_xy := true
        ) as coarse_m
    from coarse
),

-- _trail_identity(): the trail a line is part of, or none.
named as (
    select
        measured.trail_line_id,
        measured.source_key,
        coalesce(aliases.trail_name, measured.name) as trail_identity,
        measured.coarse_m
    from measured
    left join aliases
        on
            measured.source_key = aliases.source_key
            and measured.name = aliases.published_spelling
    where {{ python_strip('measured.name') }} != ''
),

vertices as (
    select
        trail_line_id,
        source_key,
        trail_identity,
        unnest(st_dump(st_points(coarse_m))) as vertex
    from named
),

-- `int(x // tolerance_m)`, as CPython's float_floor_div computes it: fmod,
-- then a division of what is left, a step down where the remainder is
-- negative, and the floor of that, rounded up past a half.
divided as (
    select
        trail_line_id,
        source_key,
        trail_identity,
        st_x(struct_extract(vertex, 'geom')) as x,
        st_y(struct_extract(vertex, 'geom')) as y,
        fmod(
            st_x(struct_extract(vertex, 'geom')),
            {{ var('trail_lines_network_chain_tolerance_m') }}
        ) as x_remainder,
        fmod(
            st_y(struct_extract(vertex, 'geom')),
            {{ var('trail_lines_network_chain_tolerance_m') }}
        ) as y_remainder
    from vertices
),

stepped as (
    select
        trail_line_id,
        source_key,
        trail_identity,
        (x - x_remainder)
        / {{ var('trail_lines_network_chain_tolerance_m') }}
        - case when x_remainder < 0 then 1.0 else 0.0 end as x_quotient,
        (y - y_remainder)
        / {{ var('trail_lines_network_chain_tolerance_m') }}
        - case when y_remainder < 0 then 1.0 else 0.0 end as y_quotient
    from divided
),

cells as (
    select distinct
        trail_line_id,
        source_key,
        trail_identity,
        cast(
            floor(x_quotient)
            + case when x_quotient - floor(x_quotient) > 0.5 then 1 else 0 end
            as bigint
        ) as cell_x,
        cast(
            floor(y_quotient)
            + case when y_quotient - floor(y_quotient) > 0.5 then 1 else 0 end
            as bigint
        ) as cell_y
    from stepped
),

-- Two lines of one identity with a vertex in one cell, both ways round.
edges as (
    select distinct
        here.trail_line_id as from_id,
        there.trail_line_id as to_id
    from cells as here
    inner join cells as there
        on
            here.source_key = there.source_key
            and here.trail_identity = there.trail_identity
            and here.cell_x = there.cell_x
            and here.cell_y = there.cell_y
            and here.trail_line_id != there.trail_line_id
),

walk (trail_line_id, chain_label) as (
    select
        trail_line_id,
        trail_line_id as chain_label
    from named
    union
    select
        edges.to_id,
        walk.chain_label
    from walk
    inner join edges on walk.trail_line_id = edges.from_id
    where edges.to_id > walk.chain_label
),

chains as (
    select
        trail_line_id,
        min(chain_label) as chain_label
    from walk
    group by trail_line_id
),

chained as (
    select
        named.trail_line_id,
        named.trail_identity,
        chains.chain_label,
        st_length(named.coarse_m) / 1609.344 as coarse_miles
    from named
    inner join chains on named.trail_line_id = chains.trail_line_id
),

summed as (
    select
        *,
        sum(coarse_miles) over (partition by chain_label) as chain_miles
    from chained
)

select
    measured.trail_line_id,
    measured.source_key,
    measured.blaze_color,
    measured.trail_status,
    summed.trail_identity,
    summed.chain_label,
    -- As text, so a unit test compares it exactly (a 2.0.6 unit test
    -- rounds a double to one decimal before comparing it).
    cast(summed.chain_miles as varchar) as chain_miles,
    case
        when
            summed.chain_miles
            >= {{ var('trail_lines_network_named_trail_threshold_miles') }}
            then summed.trail_identity
    end as through_route,
    -- WKT, every vertex exact, for the same reason.
    st_astext(measured.coarse_line) as coarse_wkt
from measured
left join summed on measured.trail_line_id = summed.trail_line_id
