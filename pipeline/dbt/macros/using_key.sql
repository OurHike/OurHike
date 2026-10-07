{#- DuckDB's `using key (...)` on a recursive CTE, which keeps one row per key
    and gives each round the whole table as `recurring.<cte>`
    (int_trail_network__node_lookups' `settled`).

    It renders only where dbt executes the model. SQLFluff 4.3.0's duckdb
    dialect does not parse the clause (measured 2026-10-07: "Found
    unparsable section" on the whole query, so the lint read none of it),
    and under SQLFluff's jinja templater `execute` is not defined, as
    raw_or_empty relies on too. So the lint reads the same query without
    the clause, and dbt's compile, its unit tests and its builds run it with
    the clause. -#}
{% macro using_key(columns) -%}
    {%- if execute is defined and execute %} using key ({{ columns }}){% endif -%}
{%- endmacro %}
