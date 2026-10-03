{#-
    dbt_utils.deduplicate on DuckDB, found through the dispatch block in
    dbt_project.yml (dbt_utils has no DuckDB version, and its default drops
    every row holding a NULL; the measurement is in that block).

    Staging's dedupe (decision 40 of #1793 — Rebuild the data platform as
    dlt → dbt: seven contracted marts, a monthly refresh, published docs, and
    lighter phone downloads; pipeline/ELT.md, "One key per table") calls
    `dbt_utils.deduplicate(relation='renamed', partition_by=<key>,
    order_by=...)`. QUALIFY keeps the row whole and follows a CTE.

    `order_by` decides which copy survives. It only ever chooses between exact
    copies, because duplicates_are_exact (tests/generic/) fails the build when
    two raw rows share a key and differ in any other column. The copies can
    still differ in a server's row id (OBJECTID, Socrata's `_socrata_id`), and
    downstream publishes that id, so a model whose layer has one orders by it
    and the lowest id survives: DEC's POI models and stg_oprhp__facilities by
    objectid, the seven NYC Socrata base models by _socrata_id. That is also the copy parity.py's
    _exact_copy_reasons expects to find kept.
-#}
{% macro duckdb__deduplicate(relation, partition_by, order_by) -%}
    select *
    from {{ relation }}
    qualify row_number() over (partition by {{ partition_by }} order by {{ order_by }}) = 1
{%- endmacro %}
