-- The Hike Finder hikes whose route ships, one row each, with the ends a
-- phone routes between, its miles and its climb, as export_suggested_hikes.py's
-- build_document() and record_for() derive them from route_hikefinder.py's
-- routes artifact.
--
-- SH05: a rejected or endless route ships nothing. A `rejected` grade, or a
-- route with no ends, is dropped here, so the hike does not reach the shelf
-- at all: client/src/lib/dayHikes.ts's validSegments drops a record with
-- fewer than two ends, and a line nobody can stand behind must be absent,
-- not faint (lib/hike_route_builder.py: "a confidently wrong prediction is
-- more dangerous than an honest unknown").
--
-- SH06: a published track ships only if the phone, re-routing between its
-- samples on this build's lines, walks back the track's own length within
-- TRACK_REPRODUCTION_TOLERANCE, 10%. That number is @unvalidated in
-- export_suggested_hikes.py, which names nothing that would settle it;
-- counting the published tracks each value admits and refuses would. A track
-- step_form_route could not re-walk at all (a sample more than 150 ft from
-- any line, or no path), or one whose length rounds to 0, ships nothing
-- either: it is never handed over as a re-drawn line. Its drift is printed
-- as the record's trackReproduction.
--
-- THE NUMBERS ARE ROUNDED AS THE TWO PYTHON FILES ROUND THEM, in their order,
-- with printf, never DuckDB's round() (pipeline/ELT.md: printf matched
-- Python's round() on every value measured, round() did not): the routes
-- artifact keeps miles to 3 decimals and the record to 2, so miles are
-- round(round(x, 3), 2); every end is cut to 6 decimals; a climb is
-- round()ed to whole feet, half to even, which round_even() matched on all
-- 80,011 doubles measured (2026-10-02, DuckDB 1.5.5). A closed walk repeats
-- its first end at the end, so the phone closes it exactly as closeTheLoop
-- would (segments_for()).
--
-- SH08: the climb is absent where the walk was never priced, never 0: a
-- walk with one unmeasured edge reported as flat fails SHORT, and short is
-- what gets somebody caught by the dark. Both feet are null together.
--
-- The miles and the ends are JSON text here, because a dbt 2.0.6 unit test
-- compares a double only to one decimal and cannot hold a list; the mart
-- casts them.
with graded as (
    select * from {{ ref('int_suggested_hikes__graded') }}
),

routes as (
    select
        hike_number,
        provenance,
        grade,
        route_notes_json,
        route_closed,
        -- to_dict()'s round(self.miles, 3), the figure
        -- export_suggested_hikes.py reads back.
        cast(printf('%.3f', route_miles) as double) as listed_miles,
        route_ends,
        walked_trails,
        climb_gain_ft,
        climb_loss_ft,
        rewalk_problem,
        rewalk_ends,
        rewalk_miles,
        rewalk_climb_gain_ft,
        rewalk_climb_loss_ft
    from graded
    -- SH05: `route["grade"] == "rejected" or not route.get("ends")`.
    where
        grade != 'rejected'
        and coalesce(json_array_length(route_ends), 0) > 0
),

drifts as (
    -- track_ends(): abs(route.miles - track_miles) / track_miles, where
    -- track_miles is the artifact's 3-decimal figure, and nothing at all
    -- when it is 0 (`if not track_miles`).
    select
        hike_number,
        abs(rewalk_miles - listed_miles) / listed_miles as drift
    from routes
    where
        provenance = 'published'
        and rewalk_problem is null
        and listed_miles != 0
),

shipping as (
    select
        routes.hike_number,
        routes.provenance,
        routes.grade,
        routes.route_notes_json,
        routes.route_closed,
        routes.listed_miles,
        drifts.drift,
        case
            when routes.provenance = 'generated' then routes.route_ends
            else routes.rewalk_ends
        end as end_points,
        case
            when routes.provenance = 'generated' then routes.walked_trails
            else json('[]')
        end as trails_json,
        case
            when routes.provenance = 'generated' then routes.climb_gain_ft
            else routes.rewalk_climb_gain_ft
        end as walk_gain_ft,
        case
            when routes.provenance = 'generated' then routes.climb_loss_ft
            else routes.rewalk_climb_loss_ft
        end as walk_loss_ft
    from routes
    left join drifts on routes.hike_number = drifts.hike_number
    where
        routes.provenance = 'generated'
        or drifts.drift
        <= cast(
            {{ var('suggested_hikes_track_reproduction_tolerance') }} as double
        )
),

end_rows as (
    select
        hike_number,
        unnest(cast(end_points as json[])) as end_point,
        generate_subscripts(cast(end_points as json[]), 1) as end_position
    from shipping
),

rounded_ends as (
    select
        hike_number,
        end_position,
        [
            cast(
                printf(
                    '%.6f', cast(json_extract(end_point, '$[0]') as double)
                ) as double
            ),
            cast(
                printf(
                    '%.6f', cast(json_extract(end_point, '$[1]') as double)
                ) as double
            )
        ] as coord
    from end_rows
),

walks as (
    select
        hike_number,
        list(coord order by end_position) as coords
    from rounded_ends
    group by hike_number
),

closed_walks as (
    select
        walks.hike_number,
        -- segments_for(): the first end repeated at the end of a closed walk.
        case
            when
                shipping.route_closed
                and walks.coords[1] != walks.coords[len(walks.coords)]
                then list_append(walks.coords, walks.coords[1])
            else walks.coords
        end as walking
    from walks
    inner join shipping on walks.hike_number = shipping.hike_number
),

segments as (
    select
        hike_number,
        -- One segment of {coord, poiId} points in walking order.
        to_json(
            [
                list_transform(
                    walking,
                    lambda coord: json_object('coord', coord, 'poiId', null)
                )
            ]
        ) as segments_json
    from closed_walks
)

select
    shipping.hike_number,
    shipping.provenance,
    shipping.grade,
    shipping.route_notes_json,
    shipping.route_closed,
    -- round(route["miles"], 2), as JSON text.
    to_json(
        cast(printf('%.2f', shipping.listed_miles) as double)
    ) as miles_json,
    segments.segments_json,
    shipping.trails_json,
    cast(round_even(shipping.walk_gain_ft, 0) as integer) as climb_gain_ft,
    cast(round_even(shipping.walk_loss_ft, 0) as integer) as climb_loss_ft,
    -- f"{drift * 100:.1f}%", on a published track only.
    printf('%.1f%%', shipping.drift * 100) as track_reproduction
from shipping
inner join segments on shipping.hike_number = segments.hike_number
