-- Transformation accuracy at the staging->intermediate boundary (DBT.md's
-- testing strategy): the union's row count must be EXACTLY the sum of its
-- inputs. A silently broken union branch or an accidental filter is the
-- regression class TESTING.md treats as first-class, and a count mismatch
-- is its cheapest possible detector. Fails by returning a row.
with expected as (
    select
        (select count(*) from {{ ref('stg_atc__shelters') }})
        + (select count(*) from {{ ref('stg_atc__campsites') }})
        + (select count(*) from {{ ref('stg_atc__viewpoints') }})
        + (select count(*) from {{ ref('stg_atc__parking') }})
        + (select count(*) from {{ ref('stg_atc__privies') }})
        + (select count(*) from {{ ref('stg_atc__communities') }})
        + (
            select count(*) from {{ ref('stg_opentrail__waypoints') }}
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
