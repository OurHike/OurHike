{#-
    A review aid with two thresholds (decision 204): the rows of `model` that
    `named` names, each with `total_rows`, the model's rows. A warning when
    any row is named, the rows a person should read; an error when at least
    `error_share` of them are (1, every row: the reader or the rule broke
    wholesale, rather than some rows needing a look). macros/test_levels.sql's
    named_rows_level() scores it, so `failures` is a level, and the rows stay
    what dbt's log, build_marts.py's failed_test_rows() and store_failures
    show.

    `named` is a boolean expression over the model's columns; a null counts as
    not named, as dbt_utils.expression_is_true's `not (...)` leaves a null
    row out. Given `to` and `field`, `column_name` names the rows whose value
    is not one of `to`'s, a relationships test's orphans, nulls left out as
    that test leaves them.
-#}
{% test rows_named(
    model, named=none, column_name=none, to=none, field=none, error_share=1
) %}
{{ config(
    fail_calc=named_rows_level(error_share), warn_if=">0", error_if=">1"
) }}
with totals as (
    select count(*) as total_rows from {{ model }}
)

select
    checked.*,
    totals.total_rows
from {{ model }} as checked
cross join totals
{%- if to is not none %}
where
    checked.{{ column_name }} is not null
    and checked.{{ column_name }} not in (
        select {{ field }} from {{ to }} where {{ field }} is not null
    )
{%- else %}
where {{ named }}
{%- endif %}
{% endtest %}
