-- A CLUB NOTICE SOURCE WHOSE RAW TABLE IS ABSENT IS HELD, WITH A REASON
-- (decision 61; pipeline/ELT.md, Phase F, "What this does not settle"). The
-- hourly warehouse can lack a notices table: one still waiting its turn in
-- the 4-hourly notices legs (a table with no hints is never created empty),
-- one the served copy of the notices store left out, or every one when the
-- hourly build read no copy at all. Each generated base model reads such a
-- table as typed and empty (macros/notices.sql's notice_raw_table), so the
-- build never fails on the missing relation, and int_closures__gate must
-- then hold the source, never pass it as "no notices"
-- (int_closures__notice_tables is what it reads). This reads the catalogue
-- itself, so a gate that stopped reading that model fails here.
--
-- Returns one row per generated notice source whose raw table is not in the
-- warehouse and that has no gate row, passes, or is held with no reason.
-- Every generated sources block declares `schema: raw`
-- (pipeline/generate_notice_models.py), which is the schema read here.
--
-- The fixture build exercises it as well as the hourly lane: on 3df39f10,
-- four notice tables have no fixture rows and are never created
-- (raw_bmta__bmta_alerts_pdf, raw_ouachita__foot_hiker_alert_mm195,
-- raw_tatc__tatc_ridgerunner_reports and
-- raw_trustees__trustees_hunting_designations).
-- tests/test_dbt_notice_tables_absent_builds.py builds with every one gone.
with readers as (
    select
        source_key,
        raw_table
    from {{ ref('notice_readers') }}
    where staged_by != 'hand'
),

present as (
    select table_name
    from information_schema.tables
    where
        table_catalog = current_database()
        and table_schema = 'raw'
),

absent as (
    select
        readers.source_key,
        readers.raw_table
    from readers
    left join present on readers.raw_table = present.table_name
    where present.table_name is null
),

gate as (
    select * from {{ ref('int_closures__gate') }}
)

select
    absent.source_key,
    absent.raw_table,
    gate.passed,
    gate.held_because
from absent
left join gate on absent.source_key = gate.source_key
where
    gate.source_key is null
    or gate.passed
    or gate.held_because is null
