-- Every point of int_points_of_interest__classified outside the box its source
-- publishes in, one row each, at warn: the strays a publisher's own typo
-- makes, which assert_pois_land_in_the_region_this_build_covers.sql lets
-- through at the layer level (its header has the three USFS sites the first
-- live monthly run found, 2026-10-03). Listed so a run log names them; the
-- points_of_interest mart's region test fails if one ships.
{{ config(severity='warn') }}

{{ lands_outside_its_region(
    ref('int_points_of_interest__classified'), 'st_point(lon, lat)'
) }}
