{#-
    How many rows a base or staging model's dedupe removed from its raw table,
    as one row (`raw_rows`, `model_rows`), with two thresholds (decision 204):
    a warning for any copy removed, an error once the copies are half the raw
    table or more (macros/test_levels.sql's dedupe_copies_level(), so
    `failures` is a level). Each copy is exact, which duplicates_are_exact on
    the raw table holds at error, so a few say only that the publisher serves
    repeats; half the table is a doubled page or a key that no longer tells
    rows apart. Measured before this rule: 3 warnings of 1 copy each on the
    fixture build, and 11 of 1 to 44 copies on UA's monthly page of
    2026-10-10.

    A raw table that does not exist in this warehouse has no rows to compare,
    and passes: pipeline/make_dbt_staging.py's base models read their raw
    table through raw_or_empty() (macros/raw_or_empty.sql), so a layer that
    has never landed reads as no rows rather than stopping the build, and a
    test that errored on a missing table would still fail it, whatever its
    severity (measured on dbt 2.0.6, 2026-10-15: a warn test that cannot run
    skips the model below it). This replaced dbt_utils.equal_rowcount, which
    errors on a missing table and counts a difference with no threshold of its
    own.
-#}
{% test equal_rowcount_to_raw(model, compare_model) %}
{{ config(fail_calc=dedupe_copies_level(), warn_if=">0", error_if=">1") }}
{%- set can_look = execute is defined and execute -%}
{%- set can_look = can_look and load_relation is defined -%}
{%- if can_look and load_relation(compare_model) is none %}
select 0 as raw_rows, 0 as model_rows
{%- else %}
select
    (select count(*) from {{ compare_model }}) as raw_rows,
    (select count(*) from {{ model }}) as model_rows
{%- endif %}
{% endtest %}
