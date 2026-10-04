{{ config(materialized='table') }}
-- Whether each club notice source's raw table is in this warehouse at all
-- (decision 61; pipeline/ELT.md, Phase F, "What this does not settle"). The
-- hourly warehouse adds the newest served copy of the 4-hourly notices
-- store, so a notices table can be absent from it: one still waiting its
-- turn (a table with no hints is never created empty), one a served copy
-- left out, or every one when the build read no copy at all. Each generated
-- base model reads an absent table as typed and empty (macros/notices.sql's
-- notice_raw_table), so nothing fails on the missing relation, and
-- int_closures__gate reads this to hold such a source with that reason,
-- whatever the run log says: a proven zero in the log says nothing about a
-- table this warehouse does not hold.
--
-- Read from DuckDB's own catalogue, in the schema every generated sources
-- block declares (`raw`), at build time, as notice_raw_table() reads it.
with readers as (
    select
        source_key,
        raw_table
    from {{ ref('notice_readers') }}
),

present as (
    select table_name
    from information_schema.tables
    where
        table_catalog = current_database()
        and table_schema = 'raw'
)

select
    readers.source_key,
    readers.raw_table,
    present.table_name is not null as is_present
from readers
left join present on readers.raw_table = present.table_name
