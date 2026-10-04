{#-
    dbt_utils.equal_rowcount between a generated base model and its raw
    table, except that a raw table that does not exist in this warehouse
    has no rows to compare, and passes.

    pipeline/make_dbt_staging.py's base models read their raw table through
    raw_or_empty() (macros/raw_or_empty.sql), so a layer that has never
    landed reads as no rows rather than stopping the build. dbt_utils'
    test compares against the raw table itself, and errors on a missing
    one: a warn-severity test that errors still fails the build. This is
    that test with duplicates_are_exact's guard. At parse time it calls
    dbt_utils' own macro, which sets the test's fail_calc.
-#}
{% test equal_rowcount_to_raw(model, compare_model) %}
{%- set can_look = execute is defined and execute -%}
{%- set can_look = can_look and load_relation is defined -%}
{%- if can_look and load_relation(compare_model) is none %}
select 0 as diff_count
{%- else %}
{{ dbt_utils.default__test_equal_rowcount(model, compare_model, []) }}
{%- endif %}
{% endtest %}
