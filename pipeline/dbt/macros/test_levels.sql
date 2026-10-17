{#-
    THE `fail_calc` OF A TEST WHOSE ERROR IS A SHARE OF ITS INPUT, AND OF AN
    ELEMENTARY CHECK'S, AS A LEVEL (the maintainer, 2026-10-15:
    "Every test should have both the warning and error thresholds").

    dbt compares one number, a test's `failures`, with both of its
    thresholds, so a rule whose error is a share (every row the test reads,
    half of a raw table) cannot be two counts. Each macro here turns what the
    test returned into 0 (pass), 1 (warn) or 2 (error), and the test declares
    `warn_if: ">0"` and `error_if: ">1"`. `failures` is then a level, not a
    count of rows, so macros/data_quality.sql writes no value for these
    tests (its `level_tests`), and the page says that a test warned or failed
    without a number.

    Measured on dbt 2.0.6 in a scratch project (2026-10-15): a project macro
    called in a generic or a singular test's config() renders into its
    `fail_calc`, the test's own config() wins over dbt_project.yml's
    defaults, and with four rows, three of them named, the "every row" rule
    warned (1) while the "half" rule failed (2).
-#}

{#- A test that returns the rows it names, each carrying `total_rows`, the
    rows of the input it reads: an error when at least `error_share` of them
    are named (1, every row: the reader or the rule broke, rather than some
    rows needing a look), a warning when any is. -#}
{% macro named_rows_level(error_share=1) -%}
case when count(*) = 0 then 0 when count(*) >= max(total_rows) * {{ error_share }} then 2 else 1 end
{%- endmacro %}

{#- equal_rowcount_to_raw's one row (`raw_rows`, `model_rows`): a warning
    for any copy the dedupe removed, an error once the copies are half of the
    raw table or more, a doubled page or a key that no longer tells rows
    apart (@unvalidated: half is the lead's pick, settled by how often a
    healthy layer's copies reach it over the first season). -#}
{% macro dedupe_copies_level() -%}
coalesce(max(case when raw_rows = model_rows then 0 when (raw_rows - model_rows) * 2 >= raw_rows and raw_rows > 0 then 2 else 1 end), 0)
{%- endmacro %}
