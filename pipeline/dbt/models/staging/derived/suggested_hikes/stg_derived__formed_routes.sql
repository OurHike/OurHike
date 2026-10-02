-- Each Hike Finder hike's route as step_form_route measured it over the
-- junction graph (pipeline/step_form_route.py), staged like any table a
-- source lands: the step writes every number as its double's repr and every
-- list as JSON text, and they are cast here, as decision 40 has staging do.
-- A repr reads back to the same double (DuckDB parses the shortest
-- round-trip digits Python prints exactly), so nothing between the search
-- and the grade rounds a measurement.
--
-- Key: the hike's number, one row per hike.
with source as (
    select * from {{ source('derived', 'formed_routes') }}
),

renamed as (
    select
        {{ dbt_utils.generate_surrogate_key([
            "'formed_routes'",
            'hike_number',
        ]) }} as formed_route_key,
        hike_number,
        provenance,
        formed_problem,
        cast(route_miles as double) as route_miles,
        cast(start_offset_m as double) as start_offset_m,
        route_closed,
        cast(retrace_ratio as double) as retrace_ratio,
        cast(climb_gain_ft as double) as climb_gain_ft,
        cast(climb_loss_ft as double) as climb_loss_ft,
        cast(route_ends as json) as route_ends,
        cast(named_trails as json) as named_trails,
        cast(walked_trails as json) as walked_trails,
        cast(route_checks as json) as route_checks,
        cast(track_gap_m as double) as track_gap_m,
        rewalk_problem,
        cast(rewalk_ends as json) as rewalk_ends,
        cast(rewalk_miles as double) as rewalk_miles,
        cast(rewalk_climb_gain_ft as double) as rewalk_climb_gain_ft,
        cast(rewalk_climb_loss_ft as double) as rewalk_climb_loss_ft,
        climb_note,
        _loaded_at as formed_at
    from source
)

{{ dbt_utils.deduplicate(
    relation='renamed', partition_by='formed_route_key', order_by='hike_number'
) }}
