{#- A raw table, or an empty one with the columns its model names, where the
    raw table does not exist in this warehouse.

    A source that has never landed is a missing table. A monthly layer the
    extract refused on its first run (extract/_run.py's ISOLATING_LANES), a
    keyed API whose key the job lacks, a notice table a conditions leg has
    not taken on yet: each one is absent, and a model that selects from a
    missing table fails the build, which skips every model downstream of it,
    every other club's rows included. So every generated base model reads
    its raw table through this, and a missing table reads as no rows.

    No rows is not "nothing there". A club layer with no rows puts nothing
    of that layer on a phone, and int_sources__publication and the gates
    downstream still decide what a source may say (int_closures__gate holds
    a notice source with no proven zero). A table that once landed never
    comes here: the extract keeps its last committed table when a later read
    fails, and the warehouse loads that.

    `columns` are the raw columns the model and the staging model above it
    name: the key, the dates, the geometry and each conformed field. Each is
    varchar in the empty table unless written `name:type`; `_loaded_at` and
    `_dlt_id` are added. dbt's load_relation() answers at run time (measured
    on dbt 2.0.6, 2026-10-03, a scratch project: a missing source built an
    empty view and a present one read its rows). Under SQLFluff's jinja
    templater, where load_relation is not defined, the macro renders the
    relation, so the lint reads the real query. -#}
{% macro raw_or_empty(relation, columns) -%}
    {%- if execute is defined and execute and load_relation is defined and load_relation(relation) is none -%}
        (
            select
                {% for column in columns -%}
                {%- set parts = column.split(':') -%}
                cast(null as {{ parts[1] if parts | length > 1 else 'varchar' }}) as "{{ parts[0] }}",
                {% endfor -%}
                cast(null as timestamptz) as _loaded_at,
                cast(null as varchar) as _dlt_id
            where false
        )
    {%- else -%}
        {{ relation }}
    {%- endif -%}
{%- endmacro %}
