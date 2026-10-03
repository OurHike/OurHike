{#-
    row_hash(relation, skip): one md5 over every column of `relation` except
    the columns `skip` names, by name and case-insensitively. It is the one
    hash of a row's content in this project: duplicates_are_exact compares
    raw copies with it, and every row-history snapshot stores it as
    `_row_hash` (macros/row_history.sql).

    Example, in the row-history snapshot of the closures mart:

        {{ row_hash(ref('int_closures__final'), row_hash_load_columns()) }}

    renders md5(cast(row("closure_id", "club", ..., "geom_geojson") as varchar)),
    every contracted column but `_loaded_at`.

    WHY row() CAST TO TEXT. DuckDB writes a struct as text with every string
    quoted where it would be ambiguous and NULL unquoted, so ('a, b', c) and
    (a, 'b, c') differ, and so do NULL and 'NULL' (measured 2026-10-03 on
    DuckDB 1.5.5, the four pairs above). A geometry is written as its WKT,
    a double in its shortest round-trip digits.

    WHAT CAN MOVE EVERY HASH AT ONCE, so that every row reads as changed in
    one build although nothing upstream did. Reasoned, none measured:
    - a DuckDB or spatial upgrade that writes a double, a timestamp or a WKT
      in different characters;
    - a TIMESTAMPTZ column printed in another session time zone, which is
      why build_marts.py runs dbt with TZ=UTC;
    - a column added to or dropped from `relation`, which changes the row()
      for every row.
    Each costs one build of false "changed" dates, never a false
    "unchanged" one, and never moves a `_first_seen_at`.

    The column list comes from the warehouse, so it is empty at parse time
    (`execute` false) and the hash is then md5 of row(null). Spelled out
    rather than written as DuckDB's *COLUMNS(* EXCLUDE ...), which dbt
    2.0.6's own SQL parser does not read (one warning per test, measured
    2026-10-01, when duplicates_are_exact was written).
-#}
{% macro row_hash(relation, skip) -%}
    {%- set skipped = skip | map('lower') | list -%}
    {%- set hashed = [] -%}
    {%- if execute -%}
        {%- for column in adapter.get_columns_in_relation(relation) -%}
            {%- if column.name | lower not in skipped -%}
                {%- do hashed.append(adapter.quote(column.name)) -%}
            {%- endif -%}
        {%- endfor -%}
    {%- endif -%}
    md5(cast(row({{ hashed | join(', ') or 'null' }}) as varchar))
{%- endmacro %}

{#- The columns a server mints per row, which differ between two copies of
    one record and say nothing about its content: OBJECTID and FID (ArcGIS),
    OGC_FID (GDAL), `_dlt_id` (dlt, at random on every load) and
    `_socrata_id` (Socrata's `:id`, which extract/_kinds.py's
    SocrataDataset lands; duplicates_are_exact's header says how its absence
    failed the monthly lane's first live build). -#}
{% macro row_hash_row_ids() -%}
    {{ return(['objectid', 'fid', 'ogc_fid', '_dlt_id', '_socrata_id']) }}
{%- endmacro %}

{#- The columns a load writes on every row whatever the row says: dlt's
    load id and `_loaded_at`, the name several staging models give
    `_loaded_at` (`loaded_at`), and `source_row`, a row's place in the raw
    table (DuckDB's rowid), which moves for every later row when one row
    upstream is added or removed. A row-history snapshot leaves these out,
    or every row would read as changed on every load: every mart carries
    `_loaded_at`. duplicates_are_exact keeps them: two copies inside one load
    share them. -#}
{% macro row_hash_load_columns() -%}
    {{ return(['_dlt_load_id', '_loaded_at', 'loaded_at', 'source_row']) }}
{%- endmacro %}
