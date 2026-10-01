{#-
    A file a phone reads, written by the model that shapes it (pipeline/ELT.md,
    "Publish (reverse ETL)", decision 24): the materialisation every pub_
    writer model sets, from dbt_project.yml's `publish` folder.

    The model is built as a table, and the table copied to
    `var('processed_dir')/<location>`. `format: json` writes the table's one
    row as one JSON document: COPY's JSON format writes each row as an object
    of its columns, so a writer selects the document's top-level fields as
    columns, and nested lists and objects as JSON values. The materialisation
    probe's gdal_file.sql, measured on dbt 2.0.6 against the Python writers,
    came out byte-identical apart from one trailing newline (ELT.md).

    `location` is a file name and never a path: DuckDB's COPY creates no
    directory (measured 2026-10-01 on DuckDB 1.5.5, "Cannot open file ...:
    No such file or directory"), so a nested location fails on any machine
    where its folder does not exist yet. The phone's own key, which may hold
    a slash, is the exposure's meta.r2_keys.

    Writers run after every other test has passed (dbt_project.yml's
    `publish` folder says why), so nothing here re-checks the data.
-#}
{% materialization phone_file, adapter='duckdb' %}
  {%- set target_relation = this.incorporate(type='table') -%}
  {%- set name = config.require('location') -%}
  {%- set format = config.require('format') -%}
  {%- if format != 'json' -%}
    {{ exceptions.raise_compiler_error("phone_file writes format 'json' so far, not '" ~ format ~ "'") }}
  {%- endif -%}
  {%- if '/' in name or '\\' in name or name.startswith('.') -%}
    {{ exceptions.raise_compiler_error("phone_file's location is a file name in processed_dir, not '" ~ name ~ "'") }}
  {%- endif -%}
  {%- set location = var('processed_dir') ~ '/' ~ name -%}
  {#- A custom materialisation enforces no contract unless it asks: without
      this, a writer whose contract named a wrong type built and wrote its
      file (measured 2026-10-01 on dbt 2.0.6). It is the check dbt-duckdb's
      table materialisation makes, which holds the marts to theirs. -#}
  {%- if config.get('contract', {}).get('enforced', false) -%}
    {{ get_assert_columns_equivalent(compiled_code) }}
  {%- endif -%}
  {{ run_hooks(pre_hooks) }}
  {% call statement('main') -%}
    create or replace table {{ target_relation }} as ({{ compiled_code }})
  {%- endcall %}
  {% call statement('write_file') -%}
    copy (select * from {{ target_relation }}) to '{{ location }}' (format json)
  {%- endcall %}
  {{ run_hooks(post_hooks) }}
  {{ adapter.commit() }}
  {{ return({'relations': [target_relation]}) }}
{% endmaterialization %}
