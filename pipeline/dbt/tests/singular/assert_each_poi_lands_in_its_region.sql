-- Every point of int_points_of_interest__classified outside the box its source
-- publishes in, one row each, with `total_rows`, every point: the strays a
-- publisher's own typo makes, which
-- assert_pois_land_in_the_region_this_build_covers.sql lets through at the
-- layer level (its header has the three USFS sites the first live monthly
-- run found, 2026-10-03). Listed so a run log names them; the
-- points_of_interest mart's region test fails if one ships. A warning for
-- any, an error when every point is outside its box (decision 204,
-- macros/test_levels.sql's named_rows_level()): the boxes or a swapped
-- reader, not a publisher's typo.
{{ config(
    fail_calc=named_rows_level(),
    warn_if='>0',
    error_if='>1',
    meta={'scores_a_level': true}
) }}

with strays as (
    {{ lands_outside_its_region(
        ref('int_points_of_interest__classified'), 'st_point(lon, lat)'
    ) }}
),

totals as (
    select count(*) as total_rows
    from {{ ref('int_points_of_interest__classified') }}
)

select
    strays.*,
    totals.total_rows
from strays
cross join totals
