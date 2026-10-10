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

    `format: json_document` is for a file COPY's JSON format cannot write:
    one whose top-level keys are data, not columns (spurs.json is one object
    keyed by side-trail id), one whose top level is not an object
    (elevation_profile.json is a bare array), or one whose records leave a
    field out rather than write it null. The model selects ONE column, the
    whole file as JSON text under any name, and it is written verbatim:
    COPY's CSV format with no header, no quoting and no escaping, which
    writes the text as it is plus one newline (measured 2026-10-02 on DuckDB
    1.5.5 by the tl-at worker: `{"side_trails:a":{"name":"x"},"side_trails:b":1}`
    came out byte for byte; and by the el worker through dbt 2.0.6 with the
    6,982,130-byte elevation_profile.json, every comma and quote as
    written). The delimiter is \x01, which no DuckDB JSON text holds raw,
    because JSON escapes every control character, and with one column none
    is written anyway. A second column fails before anything is written.

    EVERY FORMAT WRITES EXACTLY ONE ROW, the one document. Two rows fail
    before anything is written: COPY's JSON format would write them as two
    lines, which is not one JSON document. Zero rows fail too, unless the
    model sets `meta: {when_empty: 'keep_last_file'}`, in which case nothing
    is written, the run succeeds, and the job log says so. (Under `meta`,
    because dbt 2.0.6 refuses a config key it does not know, dbt1060.) That
    is for a file
    whose writer has a reason not to publish this run that is not an error:
    an ATC review nobody has done yet, which export_atc_updates.py meets by
    writing nothing and exiting 0. The writer says when with a `where`, so
    the reason is in its SQL beside the rest of its rules. The default,
    `when_empty: 'fail'`, keeps a writer that selects nothing by mistake from
    passing as one that chose to. Stage 4's upload reads a file that is not
    there as "keep the last good one", and never as an empty file. Measured
    2026-10-02 on dbt 2.0.6, one model per case: one row wrote; zero rows
    under keep_last_file wrote nothing and succeeded; zero rows by default,
    two rows, a two-column json_document and an unknown when_empty each
    failed with their message and wrote nothing.

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
  {%- set when_empty = (config.get('meta') or {}).get('when_empty', 'fail') -%}
  {%- if format not in ('json', 'json_document') -%}
    {{ exceptions.raise_compiler_error("phone_file writes format 'json' or 'json_document', not '" ~ format ~ "'") }}
  {%- endif -%}
  {%- if when_empty not in ('fail', 'keep_last_file') -%}
    {{ exceptions.raise_compiler_error("phone_file's when_empty is 'fail' or 'keep_last_file', not '" ~ when_empty ~ "'") }}
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
  {#- run_query inside a materialisation answers with real values on dbt
      2.0.6: `count(*) > 0` read back as the booleans false and true on a
      zero-row and a one-row model (measured 2026-10-02). -#}
  {%- set rows = run_query("select count(*) from " ~ target_relation).columns[0].values()[0] | int -%}
  {%- if format == 'json_document' -%}
    {%- set columns = run_query("select count(*) from (describe " ~ target_relation ~ ")").columns[0].values()[0] | int -%}
    {%- if columns != 1 -%}
      {{ exceptions.raise_compiler_error("phone_file json_document writes one column, the document, and " ~ model.name ~ " has " ~ columns) }}
    {%- endif -%}
  {%- endif -%}
  {%- if rows == 0 and when_empty == 'keep_last_file' -%}
    {{ log("phone_file " ~ model.name ~ ": nothing to write this run, so " ~ name ~ " is not written and the last good file stays (when_empty: keep_last_file)", info=true) }}
  {%- elif rows != 1 -%}
    {{ exceptions.raise_compiler_error("phone_file writes exactly one row, the document, and " ~ model.name ~ " has " ~ rows ~ (", and when_empty is 'fail'" if rows == 0 else "")) }}
  {%- elif format == 'json_document' -%}
    {% call statement('write_file') -%}
      copy (select * from {{ target_relation }}) to '{{ location }}'
      (format csv, header false, quote '', escape '', delimiter e'\x01')
    {%- endcall %}
  {%- else -%}
    {% call statement('write_file') -%}
      copy (select * from {{ target_relation }}) to '{{ location }}' (format json)
    {%- endcall %}
  {%- endif %}
  {{ run_hooks(post_hooks) }}
  {{ adapter.commit() }}
  {{ return({'relations': [target_relation]}) }}
{% endmaterialization %}
