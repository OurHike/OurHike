-- Where a POI layer cannot be: a source of int_points_of_interest__classified
-- with more than half its points, or more than 10 of them, outside the box it
-- publishes in. One row per such source.
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
-- WHY A LAYER AND NOT A ROW. A swap, or a layer read in the wrong spatial
-- reference, moves every point of the layer, so it fails here at any size.
-- A publisher's own typo moves one point, and the first live monthly run to
-- reach this test (refresh-reference.yml run 37121837559, 2026-10-03) failed
-- on three of those, all in USFS's Region 01 recreation sites, read from the
-- live layer the same day: SKALKAHO 014 at lat -48.68, lon -162.18; SKALKAHO
-- 020B at lat 60.78, lon -31.24; WILLOUGHBY 40 at lat 46.46, lon +113.99.
-- Three of 31,415 rows is not a swap. They are listed one by one by
-- assert_each_poi_lands_in_its_region.sql, at warn, and the points_of_interest
-- mart's own region test fails if one of them ever ships. Today the corridor
-- drops them, as export_nearby_poi.py's clip does: no trail is near them.
--
-- @unvalidated The 10 is picked: three times the most strays one source
-- had on the first live run. What would settle it is the count of strays
-- per source over several monthly runs.
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

with outside as (
    {{ lands_outside_its_region(
        ref('int_points_of_interest__classified'), 'st_point(lon, lat)'
    ) }}
),

outside_by_source as (
    select
        source_key,
        count(*) as outside
    from outside
    group by source_key
),

located as (
    select
        source_key,
        count(*) as located
    from {{ ref('int_points_of_interest__classified') }}
    where lon is not null and lat is not null
    group by source_key
)

select
    outside_by_source.source_key,
    located.located,
    outside_by_source.outside
from outside_by_source
inner join located
    on outside_by_source.source_key = located.source_key
where
    outside_by_source.outside > 10
    or outside_by_source.outside * 2 > located.located
