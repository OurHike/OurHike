{% macro generate_schema_name(custom_schema_name, node) -%}
    {#- The standard override DBT.md's conventions call for: a model's
        +schema IS its schema (staging/intermediate/marts/seeds), not
        "<target_schema>_<custom>", because everything lives in one DuckDB
        file rather than per-developer databases. -#}
    {%- if custom_schema_name is none -%}
        {{ target.schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
