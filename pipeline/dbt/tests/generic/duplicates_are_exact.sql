{#-
    Fails when two raw rows share a key and differ in any other column.

    Staging dedupes on its key (dbt_utils.deduplicate, whose DuckDB version is
    macros/duckdb__deduplicate.sql), and a dedupe on a key that
    is missing a column deletes a real feature: DEC's primitive campsites hold
    two different sites under one ASSET_UID (measured 2026-10-01), so a key of
    ASSET_UID alone would have dropped one of them. This test is what makes
    the dedupe safe. It passes only when every row the dedupe drops is an
    exact copy of the row it keeps, the server's own row ids aside, and it
    fails at error, because the answer to a failure is a better key, never a
    quieter test.

    `key_columns` are the same expressions the staging model passes to
    dbt_utils.generate_surrogate_key; tests/test_dbt_keys.py holds the two
    lists equal. `row_id_columns` are the columns a server mints per row
    (OBJECTID, FID), which differ between two copies of one record.
-#}
{% test duplicates_are_exact(
    model, key_columns, row_id_columns=['objectid', 'fid', 'ogc_fid', '_dlt_id']
) %}

{#- Every column but the row ids, by name. Spelled out rather than written as
    DuckDB's *COLUMNS(* EXCLUDE ...), which dbt 2.0.6's own SQL parser does
    not read (one warning per test, measured 2026-10-01). -#}
{%- set compared = [] -%}
{%- if execute -%}
{%- set row_ids = row_id_columns | map('lower') | list -%}
{%- for column in adapter.get_columns_in_relation(model) -%}
{%- if column.name | lower not in row_ids -%}
{%- do compared.append(adapter.quote(column.name)) -%}
{%- endif -%}
{%- endfor -%}
{%- endif %}

with keyed as (
    select
        {{ dbt_utils.generate_surrogate_key(key_columns) }} as key_value,
        md5(cast(row({{ compared | join(', ') or 'null' }}) as varchar))
            as row_hash
    from {{ model }}
)

select
    key_value,
    count(*) as rows_on_key,
    count(distinct row_hash) as distinct_rows
from keyed
group by key_value
having count(distinct row_hash) > 1

{% endtest %}
