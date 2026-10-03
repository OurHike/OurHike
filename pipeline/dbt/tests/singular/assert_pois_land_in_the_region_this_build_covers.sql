-- Where a POI cannot be: a row of int_points_of_interest__classified whose
-- point lies outside the box its source publishes in.
--
-- THE HOLE THIS CLOSES WAS PROVEN, NOT SUSPECTED. During Phase D's review a
-- verifier swapped the `st_x`/`st_y` lines in one staging model and rebuilt:
-- `PASS=145 WARN=0 ERROR=0`, a completely green run, with every DEC lean-to
-- relocated to Antarctica. `dbt_utils.accepted_range` did not catch it,
-- because a transposed pair is still inside +/-180 and +/-90, and the
-- reconciliation tests could not, because they compare ROW COUNTS. The union
-- is by name now (int_points_of_interest__unioned), which closes the route
-- that swap took, but a swap inside one staging model still unions cleanly,
-- so this stays (pipeline/ELT.md, "Geometry rules every mart obeys").
--
-- A POI in the wrong place is CLAUDE.md's first way this app can hurt
-- somebody - lost - so the asymmetry is the usual one: this test is allowed to
-- miss a subtle error, and is not allowed to pass a gross one.
--
-- THE BOXES are macros/lands_outside_its_region.sql's, with what each rests
-- on: the eastern box for every POI source but `usfs_rec_sites`, which is
-- nationwide and keeps the national bound. The closures, warnings,
-- trail_lines and trail_network marts run the same boxes through the generic
-- test lands_in_the_region_its_source_publishes_in.
--
-- Fails by returning rows, like every singular test here.
{{ config(severity='error') }}

{{ lands_outside_its_region(
    ref('int_points_of_interest__classified'), 'st_point(lon, lat)'
) }}
