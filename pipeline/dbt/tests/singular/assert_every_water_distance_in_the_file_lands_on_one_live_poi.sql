-- Every distance reference/water_distance.json states for an A.T. shelter
-- or campsite reaches the POI it is about. One row per distance that does
-- not: the file's poi_id, the site's name, the distance, and why.
--
-- THE HOLE. The file is keyed by the POI identity ledger's id for each site
-- (build_water_distance.py's poi_id_for(); #1729 - The water-distance join
-- is keyed by bare ATC GlobalID, nothing runs its --check, and the CSI
-- figure carries no as-of date), and int_points_of_interest__water
-- left-joins it to the live POIs on that id. A poi_id the ledger has since
-- retired, or one mistyped by hand, joins nothing: the shelter publishes
-- with no distance, no water member and no log line, and the card says
-- nothing about water at a site ATC measured it at. Water is RELEASING.md
-- 8b's set, so this is an error in every environment.
--
-- WHAT IS HELD, for each file row with a distance on the shelters or
-- campsites layer, the rows export_poi.py's load_water_distances() reads:
--
--   1. Its poi_id is not a ledger row the ledger has RETIRED. One that is
--      is listed with the release that retired it.
--   2. Where this build publishes a poi_by_type POI under that poi_id,
--      exactly one does, carrying the file's distance. A feature whose live
--      ledger row this is publishes under the row's id
--      (int_points_of_interest__identified), so that is the file row's POI.
--
-- A file row that no POI publishes under and no retired row names is not
-- listed: a feature this build does not stage, or an id the ledger never
-- minted, which this test cannot tell apart (see WHY THROUGH THE POI
-- MODELS below). CI's fixture build loads the whole file
-- (extract/_fixtures.py's REVIEWED FILES) and stages none of the 21
-- shelters whose synthesized water id the ledger retired
-- (make_dbt_fixtures.py's `kept`; 21 such rows with a distance, measured
-- on the fixture warehouse 2026-11-04), and on a live build a feature ATC
-- removed leaves the file at the next regeneration while
-- reconcile_poi_identity.py retires its row, which rule 1 then lists. An
-- id the ledger never minted is held before any build:
-- tests/test_build_water_distance.py holds the two checked-in files to
-- "every poi_id is a live ledger row" in the pytest job on the pull request
-- that commits them, and base_atc__water_distance's relationships test
-- holds every row, distance or not, to the same at the project's switch.
--
-- WHY THROUGH THE POI MODELS, and not base_ourhike__poi_identity. In
-- production a failure here holds every file below each model this test
-- reads at its last good copy (build_marts.py's failure_holds() takes the
-- test's depends_on as its roots). The ledger's base model also feeds
-- int_podcasts__checked, so reading it held the podcast episodes file as
-- well: 36 pub_ writers, against the 35 that
-- assert_no_live_poi_reuses_a_retired_id.sql (which reads the ledger's
-- retired rows as the points_of_interest mart's tombstones) and
-- assert_pois_land_in_the_region_this_build_covers.sql hold, counted with
-- failure_holds() over the manifest's child_map on 2026-11-04. Reading the
-- retired rows from int_points_of_interest__retired, the model those
-- tombstones come from, holds the same 35. What it gives up is the live
-- ledger rows, which no POI-only model carries whole, and with them the
-- "never minted" reason, which the two checks above already hold.
--
-- Measured 2026-11-04 on the committed files: 512 rows, 305 with a
-- distance, every poi_id a live ledger row, and 0 rows here on the fixture
-- warehouse. On copies of it: 1 row with one file row pointed at a retired
-- atc_csi id; 1 row with one published shelter's distance taken off it;
-- and 0 with one file row pointed at an id the ledger never minted, which
-- the relationships test lists instead.
-- int_points_of_interest__water_drops_a_distance_keyed_by_any_id_but_the_
-- published_one (_points_of_interest__unit_tests.yml) pins the silent drop
-- this test turns loud.
--
-- Fails by returning rows, like every singular test here.
{{ config(severity='error') }}

with distances as (
    select
        poi_id,
        layer,
        atc_name,
        distance_ft
    from {{ ref('base_atc__water_distance') }}
    where
        distance_ft is not null
        and layer in ('shelters', 'campsites')
),

retired as (
    select
        poi_id,
        cast(retired as varchar) as retired
    from {{ ref('int_points_of_interest__retired') }}
),

published as (
    select
        poi_id,
        water_distance_ft
    from {{ ref('int_points_of_interest__water') }}
    where
        phone_files = 'poi_by_type'
        and source in ('atc_shelters', 'atc_campsites')
),

landed as (
    select
        distances.poi_id,
        distances.layer,
        distances.atc_name,
        distances.distance_ft,
        retired.retired,
        count(published.poi_id) as pois_under_the_id,
        count(
            case
                when published.water_distance_ft = distances.distance_ft
                    then 1
            end
        ) as pois_carrying_the_distance
    from distances
    left join retired on distances.poi_id = retired.poi_id
    left join published on distances.poi_id = published.poi_id
    group by
        distances.poi_id,
        distances.layer,
        distances.atc_name,
        distances.distance_ft,
        retired.retired
),

judged as (
    select
        poi_id,
        layer,
        atc_name,
        distance_ft,
        retired,
        pois_under_the_id,
        pois_carrying_the_distance,
        case
            when retired is not null
                then 'the ledger retired this poi_id on ' || retired
            when pois_under_the_id = 0
                then null
            when pois_carrying_the_distance != 1
                then
                    'the POI this build publishes under this poi_id '
                    || 'carries no such distance'
        end as reason
    from landed
)

select
    poi_id,
    layer,
    atc_name,
    distance_ft,
    retired,
    pois_under_the_id,
    pois_carrying_the_distance,
    reason
from judged
where reason is not null
