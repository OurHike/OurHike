{#-
    Keep one row per key: the staging layer's dedupe (decision 40 of #1793 —
    Rebuild the data platform as dlt → dbt: seven contracted marts, a monthly
    refresh, published docs, and lighter phone downloads; pipeline/ELT.md,
    "One key per table").

    Not dbt_utils.deduplicate, on purpose. dbt_utils has no DuckDB version of
    that macro, and its default joins the kept rows back with a NATURAL JOIN,
    where NULL never equals NULL, so every row holding a null in any column
    disappears. Measured 2026-10-01 on DuckDB 1.5.5: of (1, 'a', NULL),
    (2, 'b', 'x'), (3, 'b', 'x') deduplicated on the second column, it kept
    only (2, 'b', 'x'). Every ATC staging model carries a null public_use, so
    that macro would have emptied them. QUALIFY keeps the row whole.

    `order_by` decides which copy survives. It only ever chooses between exact
    copies, because duplicates_are_exact (tests/generic/) fails the build when
    two raw rows share a key and differ in any other column.
-#}
{% macro dedupe(relation, key, order_by) -%}
    select *
    from {{ relation }}
    qualify row_number() over (partition by {{ key }} order by {{ order_by }}) = 1
{%- endmacro %}
