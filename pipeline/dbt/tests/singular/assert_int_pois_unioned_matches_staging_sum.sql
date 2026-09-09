-- Transformation accuracy at the staging->intermediate boundary (DBT.md's
-- testing strategy): the union's row count must be EXACTLY the sum of its
-- inputs. A silently broken union branch or an accidental filter is the
-- regression class TESTING.md treats as first-class, and a count mismatch
-- is its cheapest possible detector. Fails by returning a row.
--
-- Every branch of int_pois_unioned is listed here by hand, which is the
-- duplication that makes the test worth having: a branch dropped from the
-- union without being dropped here fails immediately, and a branch added to
-- the union without being added here does too. Thirteen branches as of
-- Phase D (#100).
with expected as (
    select
        (select count(*) from {{ ref('stg_atc__shelters') }})
        + (select count(*) from {{ ref('stg_atc__campsites') }})
        + (select count(*) from {{ ref('stg_atc__viewpoints') }})
        + (select count(*) from {{ ref('stg_atc__parking') }})
        + (select count(*) from {{ ref('stg_atc__privies') }})
        + (select count(*) from {{ ref('stg_atc__communities') }})
        + (select count(*) from {{ ref('stg_opentrail__waypoints') }})
        + (select count(*) from {{ ref('stg_dec__lean_tos') }})
        + (select count(*) from {{ ref('stg_dec__primitive_campsites') }})
        + (select count(*) from {{ ref('stg_dec__scenic_vistas') }})
        + (select count(*) from {{ ref('stg_dec__firetowers') }})
        + (select count(*) from {{ ref('stg_dec__viewing_areas') }})
        + (
            select count(*) from {{ ref('stg_dec__parking_areas') }}
        ) as row_count
),

actual as (
    select count(*) as row_count from {{ ref('int_pois_unioned') }}
)

select
    expected.row_count as expected_rows,
    actual.row_count as actual_rows
from expected
cross join actual
where expected.row_count != actual.row_count
