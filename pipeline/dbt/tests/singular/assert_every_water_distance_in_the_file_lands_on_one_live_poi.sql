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
--   1. Its poi_id is a LIVE ledger row (`retired` null). A retired row is
--      listed with the release that retired it; an id the ledger never
--      minted is a typo, or a file regenerated before the ledger was
--      reconciled (build_water_distance.py's docstring on the order).
--   2. Where this build publishes a poi_by_type POI for that ledger row's
--      feature - the same (source, source_feature_id); the ledger is the
--      one map from a file row to a staged feature - exactly one does,
--      under the file's poi_id, carrying the file's distance.
--
-- A file row whose feature this build does not stage is not a drop and is
-- not listed. CI's fixture build loads the whole file
-- (extract/_fixtures.py's reviewed_file) and stages none of the 21
-- shelters whose synthesized water id the ledger retired
-- (make_dbt_fixtures.py's `kept`; 21 such rows with a distance, measured
-- on the fixture warehouse 2026-11-04), and on a live build a feature ATC
-- removed leaves the file at the next regeneration while
-- reconcile_poi_identity.py retires its row, which rule 1 then lists.
-- tests/test_build_water_distance.py holds the two checked-in files to
-- rule 1 with no warehouse, in the pytest job, and base_atc__water_distance's
-- poi_id relationships test holds every row, distance or not, at the
-- project's switch.
--
-- Measured 2026-11-04 on the committed files: 512 rows, 305 with a
-- distance, every poi_id a live ledger row, and 0 rows here on the fixture
-- warehouse. int_points_of_interest__water_drops_a_distance_whose_poi_id_
-- the_ledger_retired (_points_of_interest__unit_tests.yml) pins the silent
-- drop this test turns loud.
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

ledger as (
    select
        poi_id,
        source,
        source_feature_id,
        cast(retired as varchar) as retired
    from {{ ref('base_ourhike__poi_identity') }}
),

published as (
    select
        poi_id,
        source,
        source_feature_id,
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
        ledger.retired,
        count(ledger.poi_id) as ledger_rows,
        count(published.poi_id) as pois_for_the_feature,
        count(
            case
                when
                    published.poi_id = distances.poi_id
                    and published.water_distance_ft = distances.distance_ft
                    then 1
            end
        ) as pois_carrying_the_distance
    from distances
    left join ledger on distances.poi_id = ledger.poi_id
    left join
        published
        on
            ledger.retired is null
            and ledger.source = published.source
            and ledger.source_feature_id = published.source_feature_id
    group by
        distances.poi_id,
        distances.layer,
        distances.atc_name,
        distances.distance_ft,
        ledger.retired
),

judged as (
    select
        poi_id,
        layer,
        atc_name,
        distance_ft,
        retired,
        pois_for_the_feature,
        pois_carrying_the_distance,
        case
            when ledger_rows = 0
                then 'the ledger has no row under this poi_id'
            when retired is not null
                then 'the ledger retired this poi_id on ' || retired
            when pois_for_the_feature = 0
                then null
            when pois_carrying_the_distance != 1
                then
                    'the POI this build publishes for the feature '
                    || 'carries no such distance under this poi_id'
        end as reason
    from landed
)

select
    poi_id,
    layer,
    atc_name,
    distance_ft,
    retired,
    pois_for_the_feature,
    pois_carrying_the_distance,
    reason
from judged
where reason is not null
