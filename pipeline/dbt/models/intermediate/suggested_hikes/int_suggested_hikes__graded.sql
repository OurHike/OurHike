-- The grade of each Hike Finder hike's route, and every check that is not
-- clean, in the order a reviewer should read them: the problems are the
-- record's `routeNotes`, word for word. step_form_route measured each route
-- over the graph (stg_derived__formed_routes); this grades the measurements,
-- in two halves, one per provenance.
--
-- A GENERATED ROUTE (SH04) is lib/hike_route_builder.py's _grade(), check for
-- check in its order: the share of the trails the description names that the
-- walk walks (rejected below TRAILS_FAIR 0.34, fair below TRAILS_GOOD 0.9),
-- the length against the publisher's stated miles (rejected past
-- LENGTH_FAIR 0.40, fair when none is stated), how much of a closed walk
-- doubles back (rejected past RETRACE_FAIR 0.60, fair past RETRACE_GOOD 0.30
-- or below RETRACE_MIN 0.03), and how far the parking sat from the line
-- (fair past START_GOOD_OFF_M, 150 m). A single failing check caps the grade;
-- they are not scored and summed, so a good number cannot hide a bad one.
-- Every one of those numbers is @unvalidated or calibrated against the 113
-- published tracks, and says which beside it in lib/hike_route_builder.py;
-- walking a sample of formed routes against their write-ups is what settles
-- the length bands (its :268-270). They are dbt_project.yml's
-- suggested_hikes_* vars, held to the Python's by
-- tests/test_dbt_suggested_hikes_parity.py.
--
-- A PUBLISHED TRACK is published_route()'s checks: never rejected for its
-- length, because the track is the publisher's own drawing and the stated
-- miles a number somebody typed, so a disagreement is reported (fair past
-- LENGTH_GOOD 0.20, and past LENGTH_FAIR 0.40 called the publisher's own two
-- figures disagreeing), as is a page that calls the walk a loop whose track
-- does not close (SH04's row carries both halves).
--
-- A route that did not form is `rejected`, its one note the step's reason.
-- Each message is printf() of Python's f-string: printf('%.1f'), '%+.0f' and
-- '%.0f' answered as Python's format did on all 40,018 doubles measured
-- (2026-10-02, DuckDB 1.5.5), ties and -0 included.
with formed as (
    select * from {{ ref('stg_derived__formed_routes') }}
),

hikes as (
    select
        hike_number,
        stated_miles,
        route_type
    from {{ ref('int_suggested_hikes__hike_finder') }}
),

measured as (
    select
        formed.hike_number,
        formed.provenance,
        formed.formed_problem,
        formed.route_miles,
        formed.start_offset_m,
        formed.route_closed,
        formed.retrace_ratio,
        formed.track_gap_m,
        hikes.stated_miles,
        hikes.route_type,
        json_array_length(formed.named_trails) as named_count,
        json_array_length(formed.walked_trails) as walked_count,
        -- FormedRoute.length_error: none where either figure is missing, or
        -- where the export states 0 (`not self.stated_miles`).
        case
            when
                formed.route_miles is not null
                and coalesce(hikes.stated_miles, 0) != 0
                then
                    (formed.route_miles - hikes.stated_miles)
                    / hikes.stated_miles
        end as length_error,
        -- (route_type or "").strip().lower() in CLOSED_ROUTE_TYPES; the var
        -- renders as a list literal, ['circuit', 'lollipop', 'out and back'].
        list_contains(
            {{ var('suggested_hikes_closed_route_types') }},
            lower({{ python_strip("coalesce(hikes.route_type, '')") }})
        ) as declared_closed
    from formed
    inner join hikes on formed.hike_number = hikes.hike_number
),

generated_checks as (
    select
        hike_number,
        case
            when named_count = 0 then 'rejected'
            when
                walked_count / named_count
                < cast({{ var('suggested_hikes_trails_fair') }} as double)
                then 'rejected'
            when
                walked_count / named_count
                < cast({{ var('suggested_hikes_trails_good') }} as double)
                then 'fair'
        end as trails_grade,
        case
            when named_count = 0
                then
                    'the description names no trail this build draws, '
                    || 'so nothing tied the route to the write-up'
            when
                walked_count / named_count
                < cast({{ var('suggested_hikes_trails_fair') }} as double)
                then
                    printf(
                        'walks %d of the %d trails the description names'
                        || ' - it is not following the write-up',
                        walked_count,
                        named_count
                    )
            when
                walked_count / named_count
                < cast({{ var('suggested_hikes_trails_good') }} as double)
                then
                    printf(
                        'walks %d of the %d trails the description names',
                        walked_count,
                        named_count
                    )
        end as trails_problem,
        case
            when length_error is null then 'fair'
            when
                abs(length_error)
                > cast({{ var('suggested_hikes_length_fair') }} as double)
                then 'rejected'
        end as length_grade,
        case
            when length_error is null
                then
                    'the export states no length, so nothing independent '
                    || 'says whether this route is the right one'
            when
                abs(length_error)
                > cast({{ var('suggested_hikes_length_fair') }} as double)
                then
                    printf(
                        '%.1f mi against the export''s %.1f mi (%+.0f%%)'
                        || ' - too far apart to be the same walk',
                        route_miles,
                        stated_miles,
                        length_error * 100
                    )
        end as length_problem,
        case
            when not route_closed or retrace_ratio is null then null
            when
                retrace_ratio
                > cast({{ var('suggested_hikes_retrace_fair') }} as double)
                then 'rejected'
            when
                retrace_ratio
                > cast({{ var('suggested_hikes_retrace_good') }} as double)
                then 'fair'
            when
                retrace_ratio
                < cast({{ var('suggested_hikes_retrace_min') }} as double)
                then 'fair'
        end as retrace_grade,
        case
            when not route_closed or retrace_ratio is null then null
            when
                retrace_ratio
                > cast({{ var('suggested_hikes_retrace_fair') }} as double)
                then
                    printf(
                        '%.0f%% of this ''%s'' is walked twice'
                        || ' - it closed as an out-and-back, not a loop',
                        retrace_ratio * 100,
                        route_type
                    )
            when
                retrace_ratio
                > cast({{ var('suggested_hikes_retrace_good') }} as double)
                then
                    printf(
                        '%.0f%% of the walk doubles back on itself',
                        retrace_ratio * 100
                    )
            when
                retrace_ratio
                < cast({{ var('suggested_hikes_retrace_min') }} as double)
                then
                    printf(
                        'a ''%s'' that retraces nothing is usually a walk'
                        || ' with too few waypoints to have gone round',
                        route_type
                    )
        end as retrace_problem,
        case
            when
                start_offset_m
                > cast({{ var('suggested_hikes_start_good_off_m') }} as double)
                then 'fair'
        end as start_grade,
        case
            when
                start_offset_m
                > cast({{ var('suggested_hikes_start_good_off_m') }} as double)
                then
                    printf(
                        'the parking sits %.0f m from the nearest line, so'
                        || ' the route starts somewhere the hiker is not',
                        start_offset_m
                    )
        end as start_problem
    from measured
    where provenance = 'generated' and formed_problem is null
),

generated_notes as (
    select
        hike_number,
        case
            when
                'rejected' in (
                    trails_grade, length_grade, retrace_grade, start_grade
                )
                then 'rejected'
            when
                'fair' in (
                    trails_grade, length_grade, retrace_grade, start_grade
                )
                then 'fair'
            else 'strong'
        end as grade,
        -- The order _grade() appends its problems in.
        list_filter(
            [trails_problem, length_problem, retrace_problem, start_problem],
            lambda note: note is not null
        ) as route_notes
    from generated_checks
),

published_checks as (
    select
        hike_number,
        case
            when length_error is null
                then
                    'the export states no length, so nothing independent '
                    || 'confirms the track is this hike''s'
            when
                abs(length_error)
                > cast({{ var('suggested_hikes_length_fair') }} as double)
                then
                    printf(
                        'the track measures %.1f mi against the export''s'
                        || ' stated %.1f mi (%+.0f%%)'
                        || ' - the publisher''s own two figures disagree',
                        route_miles,
                        stated_miles,
                        length_error * 100
                    )
            when
                abs(length_error)
                > cast({{ var('suggested_hikes_length_good') }} as double)
                then
                    printf(
                        'the track measures %.1f mi against the export''s'
                        || ' stated %.1f mi (%+.0f%%)',
                        route_miles,
                        stated_miles,
                        length_error * 100
                    )
        end as length_problem,
        case
            when declared_closed and not route_closed
                then
                    printf(
                        'the export calls this a ''%s'' but the track''s'
                        || ' ends sit %.0f m apart',
                        route_type,
                        track_gap_m
                    )
        end as closed_problem
    from measured
    where provenance = 'published' and formed_problem is null
),

published_notes as (
    select
        hike_number,
        -- published_route() sets `fair` on any check and never `rejected`.
        case
            when coalesce(length_problem, closed_problem) is not null
                then 'fair'
            else 'strong'
        end as grade,
        list_filter(
            [length_problem, closed_problem], lambda note: note is not null
        ) as route_notes
    from published_checks
),

unformed_notes as (
    select
        hike_number,
        'rejected' as grade,
        [formed_problem] as route_notes
    from measured
    where formed_problem is not null
),

graded as (
    select * from generated_notes
    union all
    select * from published_notes
    union all
    select * from unformed_notes
)

select
    formed.hike_number,
    formed.provenance,
    graded.grade,
    -- JSON text, because a unit test cannot hold a list.
    to_json(graded.route_notes) as route_notes_json,
    formed.formed_problem,
    -- What int_suggested_hikes__routed ships from, carried so it reads this
    -- model alone.
    formed.route_miles,
    formed.route_closed,
    formed.route_ends,
    formed.walked_trails,
    formed.climb_gain_ft,
    formed.climb_loss_ft,
    formed.rewalk_problem,
    formed.rewalk_ends,
    formed.rewalk_miles,
    formed.rewalk_climb_gain_ft,
    formed.rewalk_climb_loss_ft
from formed
inner join graded on formed.hike_number = graded.hike_number
