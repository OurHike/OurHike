-- Transformation accuracy at the staging->intermediate boundary (DBT.md's
-- testing strategy): the union's row count must be EXACTLY the sum of its
-- inputs. A silently broken union branch or an accidental filter is the
-- regression class TESTING.md treats as first-class, and a count mismatch
-- is its cheapest possible detector. Fails by returning a row.
--
-- Every branch of int_points_of_interest__unioned is listed here by hand,
-- which is the duplication that makes the test worth having: a branch
-- dropped from the union without being dropped here fails immediately, and
-- a branch added to the union without being added here does too. Twenty-one
-- hand-staged branches, a twenty-second for the generated club point layers,
-- which reads every one of them through int_points_of_interest__club_points,
-- and a twenty-third for GATC's water list.
with expected as (
    select
        (select count(*) from {{ ref('stg_atc__shelters') }})
        + (select count(*) from {{ ref('stg_atc__campsites') }})
        + (select count(*) from {{ ref('stg_atc__viewpoints') }})
        + (select count(*) from {{ ref('stg_atc__parking') }})
        + (select count(*) from {{ ref('stg_atc__privies') }})
        + (select count(*) from {{ ref('stg_atc__communities') }})
        + (select count(*) from {{ ref('stg_opentrail__waypoints') }})
        + (select count(*) from {{ ref('stg_oprhp__facilities') }})
        + (select count(*) from {{ ref('stg_dec__lean_tos') }})
        + (select count(*) from {{ ref('stg_dec__primitive_campsites') }})
        + (select count(*) from {{ ref('stg_dec__scenic_vistas') }})
        + (select count(*) from {{ ref('stg_dec__firetowers') }})
        + (select count(*) from {{ ref('stg_dec__viewing_areas') }})
        + (select count(*) from {{ ref('stg_dec__parking_areas') }})
        + (select count(*) from {{ ref('stg_dec__backcountry_features') }})
        + (select count(*) from {{ ref('base_usfs__rec_sites') }})
        + (select count(*) from {{ ref('base_nycparks__nyc_public_restrooms') }}
        )
        + (
            select count(*)
            from {{ ref('base_nycparks__nyc_drinking_fountains') }}
        )
        + (select count(*) from {{ ref('stg_derived__osm_water') }})
        + (select count(*) from {{ ref('stg_derived__long_path_guide') }})
        -- The site water publishes only the sites that have some.
        + (
            select count(*) from {{ ref('stg_derived__site_water') }}
            where has_water
        )
        -- The generated club point layers, one branch for all of them.
        + (
            select count(*)
            from {{ ref('int_points_of_interest__club_points') }}
        )
        -- GATC's water list, held rows included.
        + (
            select count(*)
            from {{ ref('int_points_of_interest__gatc_water') }}
        ) as row_count
),

actual as (
    select count(*) as row_count
    from {{ ref('int_points_of_interest__unioned') }}
)

select
    expected.row_count as expected_rows,
    actual.row_count as actual_rows
from expected
cross join actual
where expected.row_count != actual.row_count
