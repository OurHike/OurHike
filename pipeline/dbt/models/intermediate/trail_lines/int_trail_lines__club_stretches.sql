{{ config(materialized='table') }}
-- Which club maintains which stretch of the A.T. (TL24-TL26):
-- export_club_sections.py with lib/club_sections.py's rules. One row per
-- run of half-mile markers one club maintains, in mile order, plus the runs
-- the centerline names no club for.
--
-- The club comes from the centerline, not the staler polygon layer
-- (lib/club_sections.py's docstring: the line was edited 2026-08-04, the
-- polygons 2024-08-15). Each marker takes the club of the nearest
-- centerline vertex within MILEPOST_SNAP_M (100 m). A tie goes to the first
-- vertex in layer order, which matches PointIndex for the tie that occurs,
-- two segments' shared end; two different places exactly as near would
-- differ, and none of the 4,395 live markers is one (measured 2026-10-02:
-- every stretch equal). sqrt(dx * dx + dy * dy) stands in for hypot(); it
-- can differ in the last bit, which matters only at such a tie or at
-- exactly 100 m.
--
-- TL25, a digit Acronym is never a club (is_attributable): empty or all
-- ASCII digits is no club, and its miles publish as unattributed rather
-- than borrowing the stale polygon layer's answer. (str.isdigit() also
-- takes other scripts' digits; the live layer's 44 Acronym values are all
-- ASCII.) Today's code is wrong here, reported and kept because parity
-- holds this file to the Python: lib/club_sections.py calls the digit
-- values "an unjoined FID or a shifted column upstream", but they are the
-- Acronym field's own coded-value domain codes ('11' is KTA, '27' CMC, '0'
-- MATC, '23' RATC; the live layer's metadata, read 2026-10-02: 54 features
-- carry one of 14 such codes). Measured the same day: 33.0 of the 38.5
-- unattributed miles (66 of 77 markers) carry such a code and could be
-- decoded; the other 11 markers have no vertex within 100 m.
--
-- TL24, the runs: a new run where the club changes or two markers are more
-- than STRETCH_GAP_MILES (0.75) apart; each run owns MILEPOST_HALF_WIDTH
-- (0.25 mi) either side of its end markers. TL26: the southernmost run
-- starts at mile 0 and the northernmost ends at the last marker, a tie
-- going to the first in the order min() and max() search (the `keyed`
-- CTE).
--
-- Each layer's data is used only where that layer may publish; the Python
-- reads both unconditionally. `stretch_json` is JSON text so a unit test
-- can check it exactly.
with publication as (
    select * from {{ ref('int_sources__publication') }}
),

segments as (
    select
        segments.source_row,
        segments.club_acronym,
        segments.geom
    from {{ ref('stg_atc__centerline_segments') }} as segments
    inner join publication
        on publication.source_key = 'centerline'
    where publication.may_publish and segments.geom is not null
),

-- build_club_index(): every centerline vertex, in the layer's order, with
-- its segment's club.
vertices as (
    select
        source_row,
        part_order,
        vertex_order,
        list_extract(xy, 2) as vertex_lat,
        list_extract(xy, 1) as vertex_lon,
        case
            when
                {{ python_strip('club_acronym') }} != ''
                and not regexp_full_match(
                    {{ python_strip('club_acronym') }}, '[0-9]+'
                )
                then {{ python_strip('club_acronym') }}
        end as acronym
    from (
        select
            source_row,
            club_acronym,
            part_order,
            unnest({{ line_vertices('part_line') }}) as xy,
            generate_subscripts({{ line_vertices('part_line') }}, 1)
                as vertex_order
        from (
            select
                source_row,
                club_acronym,
                struct_extract(part, 'geom') as part_line,
                generate_subscripts(st_dump(geom), 1) as part_order
            from (
                select
                    source_row,
                    club_acronym,
                    geom,
                    unnest(st_dump(geom)) as part
                from segments
            ) as dumped
        ) as parts
    ) as flattened
),

-- A 0.002-degree grid, at least 154 m on both axes anywhere on the A.T., so
-- a vertex within 100 m of a marker lies in its cell or a neighbour.
vertex_cells as (
    select
        *,
        floor(vertex_lat / 0.002) as cell_lat,
        floor(vertex_lon / 0.002) as cell_lon
    from vertices
),

markers as (
    select
        mileposts.source_row as marker_row,
        mileposts.measure_mi as mile,
        mileposts.latitude as marker_lat,
        mileposts.longitude as marker_lon
    from {{ ref('stg_atc__half_mile_markers') }} as mileposts
    inner join publication
        on publication.source_key = 'half_mile_points_from_springer'
    where
        publication.may_publish
        and mileposts.measure_mi is not null
        and mileposts.latitude is not null
        and mileposts.longitude is not null
),

rows_around as (
    select unnest([-1, 0, 1]) as neighbour_lat
),

columns_around as (
    select unnest([-1, 0, 1]) as neighbour_lon
),

marker_cells as (
    select
        markers.*,
        floor(markers.marker_lat / 0.002) + rows_around.neighbour_lat
            as cell_lat,
        floor(markers.marker_lon / 0.002) + columns_around.neighbour_lon
            as cell_lon
    from markers
    cross join rows_around
    cross join columns_around
),

offsets as (
    select
        marker_cells.marker_row,
        vertex_cells.acronym,
        vertex_cells.source_row,
        vertex_cells.part_order,
        vertex_cells.vertex_order,
        (vertex_cells.vertex_lat - marker_cells.marker_lat)
        * {{ var('trail_lines_metres_per_degree') }} as dy,
        (vertex_cells.vertex_lon - marker_cells.marker_lon)
        * {{ var('trail_lines_metres_per_degree') }}
        * cos(
            ((marker_cells.marker_lat + vertex_cells.vertex_lat) / 2)
            * (pi() / 180.0)
        ) as dx
    from marker_cells
    inner join vertex_cells
        on
            marker_cells.cell_lat = vertex_cells.cell_lat
            and marker_cells.cell_lon = vertex_cells.cell_lon
),

nearest as (
    select
        marker_row,
        acronym
    from offsets
    where
        sqrt(dx * dx + dy * dy)
        <= {{ var('trail_lines_club_milepost_snap_m') }}
    qualify
        row_number() over (
            partition by marker_row
            order by
                sqrt(dx * dx + dy * dy), source_row, part_order, vertex_order
        ) = 1
),

attributed as (
    select
        markers.marker_row,
        markers.mile,
        nearest.acronym
    from markers
    left join nearest on markers.marker_row = nearest.marker_row
),

breaks as (
    select
        *,
        case
            when
                lag(mile) over (order by mile, marker_row) is null
                or coalesce(acronym, '')
                != coalesce(lag(acronym) over (order by mile, marker_row), '')
                or mile - lag(mile) over (order by mile, marker_row)
                > {{ var('trail_lines_club_stretch_gap_mi') }}
                then 1
            else 0
        end as starts_a_run
    from attributed
),

runs as (
    select
        *,
        cast(
            sum(starts_a_run) over (
                order by mile, marker_row rows unbounded preceding
            ) as bigint
        ) as run_order
    from breaks
),

stretches as (
    select
        run_order,
        any_value(acronym) as acronym,
        min(mile) - {{ var('trail_lines_club_milepost_half_width_mi') }}
            as start_mile,
        max(mile) + {{ var('trail_lines_club_milepost_half_width_mi') }}
            as end_mile
    from runs
    group by run_order
),

-- A key's place in lib/club_sections.build_stretches()' dict, the order its
-- first run appeared, which is the order min() and max() search in.
keyed as (
    select
        *,
        min(run_order) over (partition by coalesce(acronym, '')) as key_order
    from stretches
),

termini as (
    select
        (
            select run_order from keyed
            order by start_mile, key_order, run_order
            limit 1
        ) as southernmost,
        (
            select run_order from keyed
            order by end_mile desc, key_order asc, run_order asc
            limit 1
        ) as northernmost,
        (select max(mile) from markers) as northern_terminus
),

pinned as (
    select
        keyed.run_order,
        keyed.acronym,
        case
            when keyed.run_order = termini.southernmost
                then {{ var('trail_lines_club_springer_mile') }}
            else keyed.start_mile
        end as start_mile,
        case
            when keyed.run_order = termini.northernmost
                then termini.northern_terminus
            else keyed.end_mile
        end as end_mile
    from keyed
    cross join termini
)

select
    run_order,
    acronym,
    start_mile,
    end_mile,
    cast(
        json_object('start_mile', start_mile, 'end_mile', end_mile) as varchar
    ) as stretch_json
from pinned
