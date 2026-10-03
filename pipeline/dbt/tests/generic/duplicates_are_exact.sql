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
    (OBJECTID, FID), which differ between two copies of one record; left
    out, they are macros/row_hash.sql's row_hash_row_ids(), the list the
    row-history snapshots leave out too. Rows are compared by row_hash(),
    that file's one hash of a row.

    `_socrata_id` is one of them: Socrata's row id `:id`, which
    extract/_kinds.py's SocrataDataset lands under that name. It was missing
    here until the monthly lane's first live build (refresh-reference.yml run
    37109384156), where it failed three NYC tests on rows that differ in
    nothing else. Measured 2026-10-03 on the live rows: nyc_dot_greenways'
    10 repeated segmentids (54 rows), nyc_parks_trails' 4 repeated keys (8
    rows) and nyc_public_restrooms' 2 (4 rows) differ only in `_socrata_id`
    and `_dlt_id`. pipeline/spike_table_keys.py, which counted those copies
    on 2026-10-01, already treated `:id` as a row id; this list had not.
-#}
{% test duplicates_are_exact(model, key_columns, row_id_columns=none) %}

with keyed as (
    select
        {{ dbt_utils.generate_surrogate_key(key_columns) }} as key_value,
        {{ row_hash(model, row_id_columns if row_id_columns is not none else row_hash_row_ids()) }}
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
