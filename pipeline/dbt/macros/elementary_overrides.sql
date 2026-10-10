{#- Elementary on dbt 2 and DuckDB (decision 102, pipeline/ELT.md "Data
    quality (decision 102)").

    dbt 2 pools its connections, so a temporary table one statement creates is
    gone by the next. Elementary's own redshift__has_temp_table_support()
    answers false under dbt 2 for exactly this; its DuckDB path has no such
    branch, and without these two overrides every Elementary step that uses a
    temporary table fails: its 30 models on "Table with name
    dbt_exposures__tmp_... does not exist!", and the end of every run that
    ran an anomaly test on "Table with name data_monitoring_metrics__tmp_...
    does not exist!" (measured 2026-10-07 on Elementary 0.26.0, dbt 2.0.6 and
    DuckDB, a scratch project). With both, all 30 models built and every test
    kind ran. Both belong upstream; remove them once Elementary carries them.

    Found first through dbt_project.yml's dispatch entry for `elementary`. -#}

{#- Elementary's own intermediate tables become plain tables, which its
    clean_elementary_temp_tables() drops at the end of the run. -#}
{% macro duckdb__has_temp_table_support() %}
    {% do return(not elementary.is_dbt_fusion()) %}
{% endmacro %}

{#- insert_data_monitoring_metrics() asks for a temporary table without
    asking has_temp_table_support(), so it gets a plain table here too, and
    drops it itself. -#}
{% macro duckdb__edr_get_create_table_as_sql(temporary, relation, sql_query, expiration_hours=none) %}
    create or replace {% if temporary and elementary.has_temp_table_support() %} temporary {% endif %} table {{ relation }}
    as {{ sql_query }}
{% endmacro %}
