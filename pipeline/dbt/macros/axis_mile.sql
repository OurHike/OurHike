{#-
    The A.T. mile of every point in a relation, read off
    int_trail_lines__mile_axis by that model's recipe: the one rule for every
    consumer of the axis, so a POI's `mile`, a spur's `junction_mile`, a
    trail_miles.json vertex and the profile's `distance_mi` cannot drift
    apart by each reimplementing it. It replaces export_elevation.py's
    `STRtree(...).nearest` then `CalibratedPart.mile_at(line.project(...))`,
    which export_poi.attach_miles, export_spurs.attach_junction_miles and
    export_trails.vertex_miles each call today.

    axis_mile(points, keys, point, search_m=1000) is a query, for a CTE's
    body, with the `keys` columns of `points` and:
    - piece_id and distance_m: the point's nearest piece, in metres;
    - along_mi: how far along that piece, st_linelocatepoint(geom_5070,
      point) * length_m / mile_axis_metres_per_mile;
    - mile: mile_at_along on that piece, unrounded. Each file rounds it as its
      exporter does: trail_miles.json with numpy's np.round, a spur's
      junction_mile and a POI's mile with Python's round().

    `points` is a relation, one row per point; `keys`, a list of the columns
    that name a point in it; `point`, its column holding the point in
    EPSG:5070 metres (step 1 of the recipe, st_transform(..., 'EPSG:4326',
    'EPSG:5070', always_xy := true)).

    THE NEAREST PIECE, step 2: the least st_distance. A piece is looked for
    within `search_m` first, and among every piece only for a point with none
    that near, so the answer is the nearest whatever the distance and the
    search stays cheap for points on the trail.

    A TIE GOES TO THE PIECE THE POINT DOES NOT END (st_linelocatepoint below
    1), THEN TO THE LOWER piece_id: where one piece ends and the next begins,
    the point is read on the next, as a half-open interval reads it.
    @unvalidated as a rule. shapely's STRtree breaks a tie by its own visiting
    order, which its docstring calls possibly nondeterministic, so no SQL can
    be the Python's own rule. Measured 2026-10-02 on ATC's live centerline:
    3 of 216,767 trail_miles.json vertices tie, all at one three-way junction
    near mile 1261 where piece 373 ends at 1261.144 and pieces 374 and 375
    begin at 1261.0. The STRtree picked 374; this order picks 374; the lower
    piece_id alone picked 373, moving those three miles by 0.144 mi and
    reversing one chain's direction of travel. What settles it is the Python
    breaking ties the same way, or a tie on which the two disagree.
-#}
{% macro axis_mile(points, keys, point, search_m=1000) -%}
(
    with axis_mile_near as (
        select
            {%- for key in keys %}
            located.{{ key }},
            {%- endfor %}
            axis_piece.piece_id,
            st_distance(axis_piece.geom_5070, located.{{ point }}) as distance_m,
            st_linelocatepoint(axis_piece.geom_5070, located.{{ point }})
                as fraction
        from {{ points }} as located
        inner join {{ ref('int_trail_lines__mile_axis') }} as axis_piece
            on st_dwithin(
                axis_piece.geom_5070, located.{{ point }}, {{ search_m }}
            )
    ),

    axis_mile_unmatched as (
        select located.*
        from {{ points }} as located
        anti join axis_mile_near
            on
                {%- for key in keys %}
                {{ "and " if not loop.first }}located.{{ key }} = axis_mile_near.{{ key }}
                {%- endfor %}
    ),

    axis_mile_candidates as (
        select * from axis_mile_near
        union all
        select
            {%- for key in keys %}
            axis_mile_unmatched.{{ key }},
            {%- endfor %}
            axis_piece.piece_id,
            st_distance(
                axis_piece.geom_5070, axis_mile_unmatched.{{ point }}
            ) as distance_m,
            st_linelocatepoint(
                axis_piece.geom_5070, axis_mile_unmatched.{{ point }}
            ) as fraction
        from axis_mile_unmatched
        cross join {{ ref('int_trail_lines__mile_axis') }} as axis_piece
    ),

    axis_mile_nearest as (
        select
            axis_mile_candidates.*,
            axis_mile_candidates.fraction
            * axis_piece.length_m
            / {{ var('mile_axis_metres_per_mile') }} as along_mi,
            axis_piece.anchor_along_mi,
            axis_piece.anchor_mile
        from axis_mile_candidates
        inner join {{ ref('int_trail_lines__mile_axis') }} as axis_piece
            on axis_mile_candidates.piece_id = axis_piece.piece_id
        qualify
            row_number() over (
                partition by
                    {%- for key in keys %}
                    axis_mile_candidates.{{ key }}{{ "," if not loop.last }}
                    {%- endfor %}
                order by
                    axis_mile_candidates.distance_m,
                    axis_mile_candidates.fraction = 1,
                    axis_mile_candidates.piece_id
            ) = 1
    )

    select
        {%- for key in keys %}
        {{ key }},
        {%- endfor %}
        piece_id,
        distance_m,
        along_mi,
        {{ mile_at_along('along_mi', 'anchor_along_mi', 'anchor_mile') }} as mile
    from axis_mile_nearest
)
{%- endmacro %}
