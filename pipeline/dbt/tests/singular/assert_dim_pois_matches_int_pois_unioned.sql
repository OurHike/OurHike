-- Transformation accuracy at the intermediate->mart boundary: dim_pois adds
-- a key and nothing else, so its row count must exactly match its input's.
-- Fails by returning a row. See the staging-boundary twin for the class of
-- regression this catches.
with expected as (
    select count(*) as row_count from {{ ref('int_pois_unioned') }}
),

actual as (
    select count(*) as row_count from {{ ref('dim_pois') }}
)

select
    expected.row_count as expected_rows,
    actual.row_count as actual_rows
from expected
cross join actual
where expected.row_count != actual.row_count
